FROM python:3.13.0

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        default-libmysqlclient-dev \
        curl \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libatspi2.0-0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/

WORKDIR /app

# Copy your source code
COPY . .

# Install python dependencies
RUN pip install --upgrade cython && pip install --upgrade pip
RUN ln -sf /usr/share/zoneinfo/Europe/Copenhagen /etc/localtime
RUN pip install -r requirements.txt

# Install playwright browsers
RUN playwright install

# Default command - you can override in docker-compose
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000"]
