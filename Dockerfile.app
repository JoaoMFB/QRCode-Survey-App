# Use the Amazon Linux 2 base image
FROM amazonlinux:2

# Install Python 3, pip, and Git
RUN yum update -y && \
    yum install -y python3 python3-pip git && \
    yum clean all

# Set working directory inside the container
WORKDIR /usr/src/app

# Install dependencies first
COPY app/requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the full application code into the container
COPY app/ .

# Expose the port used by Uvicorn
EXPOSE 8000

# Start the FastAPI app using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
