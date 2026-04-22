# Usamos la imagen oficial de Playwright que ya contiene los navegadores compilados
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

# Ajuste de zona horaria nativa para el contenedor
ENV TZ=America/Puerto_Rico
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Instalamos el motor Tesseract OCR y las dependencias gráficas para OpenCV
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Definimos el directorio de trabajo
WORKDIR /app

# Optimizamos la caché de Docker copiando primero los requerimientos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código del proyecto
COPY . .

# Comando de arranque apuntando al orquestador (Scheduler)
CMD ["python", "-m", "src.scheduler"]