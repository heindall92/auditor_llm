FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000 AUDITOR_OUTPUT_DIR=/app/output/web
WORKDIR /app
RUN groupadd --gid 10001 auditor && useradd --uid 10001 --gid auditor --no-create-home auditor
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir '.[hosting]' && mkdir -p /app/output/web && chown -R auditor:auditor /app/output
USER auditor
EXPOSE 10000
CMD ["python", "-m", "agent_audit.hosted"]
