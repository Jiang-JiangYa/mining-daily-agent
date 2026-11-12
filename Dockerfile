FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mining_agent ./mining_agent
ENTRYPOINT ["python", "-m", "mining_agent.agent"]
