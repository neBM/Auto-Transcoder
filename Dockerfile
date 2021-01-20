FROM python:3
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && apt update && apt install --no-install-recommends -y ffmpeg
COPY . .
CMD ["python", "./main.py"]
VOLUME [ "/data" ]
EXPOSE 5252