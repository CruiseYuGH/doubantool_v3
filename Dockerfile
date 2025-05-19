FROM python:3.9-slim

# 安装必要的工具和依赖
RUN apt-get update && apt-get install -y \
    unzip \
    gnupg \
    curl \
    fonts-noto-cjk \
    locales \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxrender1 \
    libx11-xcb1 \
    libxcb1 \
    libdbus-glib-1-2 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 生成并设置区域设置
RUN echo "zh_CN.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen zh_CN.UTF-8 && \
    update-locale LANG=zh_CN.UTF-8

ENV LC_ALL zh_CN.UTF-8
ENV LANG zh_CN.UTF-8
ENV LANGUAGE zh_CN.UTF-8

# 根据架构条件处理 Chrome 和 Chromedriver
ARG TARGETARCH

# 对于arm64架构，安装chromium和chromedriver
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        apt-get update && \
        apt-get install -y chromium chromium-driver && \
        mkdir -p /opt/chrome-linux64 && \
        ln -s /usr/bin/chromium /opt/chrome-linux64/chrome && \
        ln -s /usr/bin/chromedriver /usr/local/bin/chromedriver; \
    fi

# 将应用程序代码复制到容器中
WORKDIR /app
COPY . .

# 仅在amd64架构下复制本地的Chrome和Chromedriver
RUN if [ "$TARGETARCH" = "amd64" ]; then \
        cp drivers/amd64/chromedriver /usr/local/bin/chromedriver && \
        cp -r drivers/amd64/chrome /opt/chrome-linux64; \
    fi

# 设置 Chromedriver 和 Chrome 的执行权限
RUN chmod +x /usr/local/bin/chromedriver && \
    chmod +x /opt/chrome-linux64/chrome

# 设置环境变量以指向 Chrome 和 Chromedriver
ENV PATH="/opt/chrome-linux64:${PATH}"
ENV CHROMEDRIVER_PATH="/usr/local/bin/chromedriver"

# 删除 /app/drivers 文件夹
RUN rm -rf /app/drivers

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量以避免 Chrome 的 "headless" 模式问题
ENV CHROME_BIN="/opt/chrome-linux64/chrome"

# 暴露 Flask 应用程序的端口
EXPOSE 5000

# 运行 Flask 应用程序和 main.py
CMD ["sh", "-c", "python main.py & python app.py"]
