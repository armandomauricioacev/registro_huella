# Usa una imagen oficial de Python
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia SOLO requirements.txt primero (mejor caché)
COPY ./api/requirements.txt /app/requirements.txt

# Instala dependencias
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copia el resto del código de la API
COPY ./api /app

# Expone el puerto donde correrá Flask
EXPOSE 5000

# Comando para ejecutar la app (ajusta si usas otro archivo o módulo)
CMD ["python", "app.py"]
