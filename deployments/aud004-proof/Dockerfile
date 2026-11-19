# Build-time dependency installation; the runtime proof network remains internal.
FROM python:3.13-slim
WORKDIR /proof
RUN python -m pip install --no-cache-dir pytest==9.2.0 psycopg2-binary==2.9.13
COPY test_acl.py /proof/test_acl.py
CMD ["python", "-m", "pytest", "-q", "/proof/test_acl.py"]
