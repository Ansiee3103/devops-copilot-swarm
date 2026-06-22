import os
import re
from utils.groq_client import ask_llm
from integrations.github_client import get_kubernetes_manifest
from backend.core.logger import get_logger

logger = get_logger("builder_agent")

# ── Language Configs ──────────────────────────────────────
LANGUAGE_CONFIGS = {
    "Go": {
        "base_image":    "golang:1.21-alpine",
        "runtime_image": "gcr.io/distroless/static-debian12",
        "package_manager": "go mod",
        "test_cmd":      "go test ./...",
        "build_cmd":     "go build -o app .",
        "port":          "8080"
    },
    "Python": {
        "base_image":    "python:3.12-slim",
        "runtime_image": "python:3.12-slim",
        "package_manager": "pip",
        "test_cmd":      "pytest",
        "build_cmd":     "pip install -r requirements.txt",
        "port":          "8080"
    },
    "Node.js": {
        "base_image":    "node:20-alpine",
        "runtime_image": "node:20-alpine",
        "package_manager": "npm",
        "test_cmd":      "npm test",
        "build_cmd":     "npm ci --only=production",
        "port":          "7000"
    },
    "Java": {
        "base_image":    "eclipse-temurin:17-jdk-alpine",
        "runtime_image": "eclipse-temurin:17-jre-alpine",
        "package_manager": "gradle",
        "test_cmd":      "./gradlew test",
        "build_cmd":     "./gradlew build -x test",
        "port":          "9555"
    },
    "C#": {
        "base_image":    "mcr.microsoft.com/dotnet/sdk:8.0",
        "runtime_image": "mcr.microsoft.com/dotnet/aspnet:8.0",
        "package_manager": "dotnet",
        "test_cmd":      "dotnet test",
        "build_cmd":     "dotnet publish -c Release -o /app/publish",
        "port":          "7070"
    }
}

def clean_output(text: str) -> str:
    """Remove markdown code blocks"""
    text = re.sub(r'```[a-zA-Z]*\n', '', text)
    text = re.sub(r'```', '', text)
    return text.strip()

def enforce_start(text: str, start: str) -> str:
    """Make sure output starts with correct keyword"""
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith(start):
            return '\n'.join(lines[i:])
    return text

# ── Dockerfile Generator ──────────────────────────────────
def generate_dockerfile(service_name: str, language: str) -> str:
    config = LANGUAGE_CONFIGS.get(language, LANGUAGE_CONFIGS["Python"])

    prompt = f"""
    Generate a production-grade, secure Dockerfile for:
    Service : {service_name}
    Language: {language}
    Config  : {config}

    STRICT REQUIREMENTS:
    1. Use multi-stage build (builder + runtime stage)
    2. Base image: {config['base_image']} for build
    3. Runtime image: {config['runtime_image']} (minimal/distroless)
    4. Run as non-root user (uid 1000)
    5. Add HEALTHCHECK instruction
    6. Set resource-friendly ENV variables
    7. Copy only necessary files to runtime
    8. Pin all versions (no :latest tags in FROM except runtime)
    9. Add proper LABELS (maintainer, version, description)
    10. EXPOSE port {config['port']}

    Return ONLY raw Dockerfile. No markdown. Start with FROM.
    """

    raw = ask_llm(prompt)
    result = clean_output(raw)
    result = enforce_start(result, "FROM")

    # Validate it starts correctly
    if not result.startswith("FROM"):
        result = f"""# {service_name} Dockerfile
FROM {config['base_image']} AS builder

WORKDIR /app
COPY . .
RUN {config['build_cmd']}

FROM {config['runtime_image']}
WORKDIR /app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --from=builder /app .
USER appuser
EXPOSE {config['port']}
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD wget -q --spider http://localhost:{config['port']}/ || exit 1
CMD ["./app"]
"""
    return result

# ── K8s Manifest Generator ────────────────────────────────
def generate_k8s_manifest(service_name: str, language: str, existing: str = "") -> str:
    config = LANGUAGE_CONFIGS.get(language, LANGUAGE_CONFIGS["Python"])

    prompt = f"""
    Generate a production-grade Kubernetes manifest for:
    Service : {service_name}
    Language: {language}
    Port    : {config['port']}

    Existing manifest reference:
    {existing[:500] if existing else 'None'}

    STRICT REQUIREMENTS:
    Generate BOTH Deployment AND Service in one file separated by ---

    Deployment requirements:
    1. apiVersion: apps/v1
    2. Replicas: 2 minimum
    3. Resource limits AND requests (cpu/memory)
    4. Liveness probe (httpGet or grpc)
    5. Readiness probe (httpGet or grpc)
    6. Security context:
       - runAsNonRoot: true
       - runAsUser: 1000
       - readOnlyRootFilesystem: true
       - allowPrivilegeEscalation: false
    7. Pod disruption budget annotation
    8. Rolling update strategy with maxUnavailable: 1
    9. Proper labels and selectors (app, version, tier)
    10. Environment variables from ConfigMap/Secret refs

    Service requirements:
    1. Type: ClusterIP
    2. Correct port mapping
    3. Proper selector matching deployment labels

    Return ONLY raw YAML. No markdown. Start with apiVersion.
    """

    raw    = ask_llm(prompt)
    result = clean_output(raw)
    result = enforce_start(result, "apiVersion")

    if not result.startswith("apiVersion"):
        result = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_name}
  labels:
    app: {service_name}
    version: v1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {service_name}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  template:
    metadata:
      labels:
        app: {service_name}
        version: v1
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
      - name: {service_name}
        image: {service_name}:latest
        ports:
        - containerPort: {config['port']}
        resources:
          requests:
            cpu: 100m
            memory: 64Mi
          limits:
            cpu: 200m
            memory: 128Mi
        livenessProbe:
          httpGet:
            path: /
            port: {config['port']}
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /
            port: {config['port']}
          initialDelaySeconds: 5
          periodSeconds: 10
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
---
apiVersion: v1
kind: Service
metadata:
  name: {service_name}
  labels:
    app: {service_name}
spec:
  type: ClusterIP
  selector:
    app: {service_name}
  ports:
  - port: {config['port']}
    targetPort: {config['port']}
    protocol: TCP
"""
    return result

# ── CI/CD Pipeline Generator ──────────────────────────────
def generate_cicd_pipeline(service_name: str, language: str) -> str:
    config = LANGUAGE_CONFIGS.get(language, LANGUAGE_CONFIGS["Python"])

    prompt = f"""
    Generate a production-grade, secure GitHub Actions CI/CD pipeline for:
    Service  : {service_name}
    Language : {language}
    Build cmd: {config['build_cmd']}
    Test cmd : {config['test_cmd']}

    STRICT SECURITY REQUIREMENTS:
    1. Pin ALL action versions to full 40-character commit SHAs to prevent supply-chain attacks. Do not use tag names like @v4 or @master. Use these exact hashes:
       - actions/checkout -> actions/checkout@692973e3d937129bcbf40652eb9f2f61becf3332 (v4.1.7)
       - actions/cache -> actions/cache@0c45773b623bea8c8e75f6c82b208c3cf94ea4f9 (v4.0.2)
       - actions/upload-artifact -> actions/upload-artifact@65462800fd760344b1a7b4382951275a0abb4808 (v4.3.3)
       - aquasecurity/trivy-action -> aquasecurity/trivy-action@18f77341fe231f476a6d68b209e9e1bbcdb4bf46 (v0.24.0)
       - google-github-actions/auth -> google-github-actions/auth@71feeae93345b6db30c11f784d2b172471cba52e (v2.1.2)
    2. Use 'permissions' block with least privilege
    3. Never hardcode secrets — use ${{{{ secrets.NAME }}}}
    4. Add Trivy security scan on both code and Docker image
    5. environment: production on deploy job

    STRICT STRUCTURE REQUIREMENTS:
    1. Three separate jobs:
       a) build-and-test (runs first)
       b) security-scan (needs build-and-test)
       c) build-push-deploy (needs security-scan)
    2. Cache dependencies for speed
    3. Upload test results as artifacts
    4. Docker image tagged with ${{{{ github.sha }}}}
    5. Kubernetes rollout verify after deploy
    6. Dry-run validation before actual deploy

    Required secrets to reference:
    - GCP_SA_KEY, GCP_PROJECT_ID
    - GKE_CLUSTER_NAME, GKE_ZONE

    Return ONLY raw YAML. No markdown. Start with 'name:'.
    """

    raw    = ask_llm(prompt)
    result = clean_output(raw)
    result = enforce_start(result, "name:")

    if not result.startswith("name:"):
        result = f"""name: {service_name} CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
  id-token: write
  security-events: write

env:
  IMAGE_NAME: {service_name}

jobs:
  build-and-test:
    name: Build & Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@692973e3d937129bcbf40652eb9f2f61becf3332 # v4.1.7
      - name: Run tests
        run: {config['test_cmd']}

  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    needs: build-and-test
    steps:
      - uses: actions/checkout@692973e3d937129bcbf40652eb9f2f61becf3332 # v4.1.7
      - name: Run Trivy scan
        uses: aquasecurity/trivy-action@18f77341fe231f476a6d68b209e9e1bbcdb4bf46 # v0.24.0
        with:
          scan-type: fs
          severity:  CRITICAL,HIGH
          exit-code: 1

  build-push-deploy:
    name: Build Push Deploy
    runs-on: ubuntu-latest
    needs: security-scan
    environment: production
    steps:
      - uses: actions/checkout@692973e3d937129bcbf40652eb9f2f61becf3332 # v4.1.7
      - name: Auth GCP
        uses: google-github-actions/auth@71feeae93345b6db30c11f784d2b172471cba52e # v2.1.2
        with:
          credentials_json: ${{{{ secrets.GCP_SA_KEY }}}}
      - name: Build image
        run: docker build -t gcr.io/${{{{ secrets.GCP_PROJECT_ID }}}}/{service_name}:${{{{ github.sha }}}} .
      - name: Push image
        run: docker push gcr.io/${{{{ secrets.GCP_PROJECT_ID }}}}/{service_name}:${{{{ github.sha }}}}
      - name: Deploy
        run: kubectl apply -f k8s-manifest.yaml
"""
    return result

# ── Main Builder Agent ────────────────────────────────────
def builder_agent(service_name: str, language: str, plan: str) -> dict:
    logger.info(f"🏗️ Builder Agent starting for {service_name} ({language})")
    print(f"\n🏗️ Builder Agent — Generating production configs for {service_name}...")

    existing_manifest = ""
    try:
        existing_manifest = get_kubernetes_manifest(service_name)
    except:
        pass

    # Generate all configs
    print("   📄 Generating Dockerfile...")
    dockerfile = generate_dockerfile(service_name, language)

    print("   ☸️  Generating K8s manifest...")
    k8s_manifest = generate_k8s_manifest(service_name, language, existing_manifest)

    print("   ⚙️  Generating CI/CD pipeline...")
    cicd_pipeline = generate_cicd_pipeline(service_name, language)

    # Save files
    output_dir = f"outputs/{service_name}"
    os.makedirs(output_dir, exist_ok=True)

    files = {
        "Dockerfile":        dockerfile,
        "k8s-manifest.yaml": k8s_manifest,
        "pipeline.yml":      cicd_pipeline
    }

    for filename, content in files.items():
        path = f"{output_dir}/{filename}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"   ✅ Saved: {path}")

    # Validate
    print(f"\n   Dockerfile  starts: {dockerfile[:40].strip()}")
    print(f"   K8s manifest starts: {k8s_manifest[:40].strip()}")
    print(f"   Pipeline     starts: {cicd_pipeline[:40].strip()}")

    logger.info(f"✅ Builder done for {service_name}")
    print(f"✅ Builder — All configs saved to {output_dir}/\n")

    return {
        "dockerfile":      dockerfile,
        "k8s_manifest":    k8s_manifest,
        "cicd_pipeline":   cicd_pipeline,
        "output_dir":      output_dir,
        "generated_files": list(files.keys())
    }