FROM python:3.11-slim

# Tizim paketlarini yangilash va eng kerakli kutubxonalarni o'rnatish
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Ishchi katalogni belgilash
WORKDIR /app

# Kutubxonalar ro'yxatini yuklash va o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Manba kodlarini nusxalash
COPY . .

# Portni belgilash (default: 8080)
EXPOSE 8080

# Botni ishga tushirish buyrug'i
CMD ["python", "main.py"]
