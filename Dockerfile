FROM python:3.11-slim
WORKDIR /app

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser && \
    chown appuser:appuser /app

# Cài CHỈ dependencies (không build package) → layer cache tốt
# tomllib có sẵn trong Python 3.11 stdlib, không cần thêm package
COPY pyproject.toml .
RUN python -c "\
import tomllib, subprocess, sys; \
deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; \
subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir'] + deps, check=True)"

# Copy source sau khi deps đã cache
COPY --chown=appuser:appuser . .
RUN mkdir -p uploads && chown appuser:appuser uploads

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-keep-alive 90"]
