#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
GIT_REPO_URL="https://github.com/vishal24989/twitter-clone.git"
REPO_DIR="twitter-clone" # The directory name that git clone will create
DEFAULT_USER="ec2-user"
HOME_DIR="/home/$DEFAULT_USER"
PROJECT_DIR="$HOME_DIR/$REPO_DIR"

# --- Create the .env file with your secrets ---
# IMPORTANT: Fill these values in before pasting into User Data.
cat > $HOME_DIR/.env <<EOF
DATABASE_URL=postgresql://user:password@db:5432/twitter_clone_db
SECRET_KEY=your_very_strong_and_long_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDIS_HOST=cache
REDIS_PORT=6379
EOF

# --- Start of Deployment ---
echo "--- Updating system packages... ---"
yum update -y

echo "--- Installing Git... ---"
yum install -y git

echo "--- Installing Docker... ---"
yum install -y docker

echo "--- Installing Docker Compose... ---"
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose

echo "--- Starting and enabling Docker service... ---"
systemctl start docker
systemctl enable docker

echo "--- Adding '$DEFAULT_USER' user to the Docker group... ---"
usermod -a -G docker $DEFAULT_USER

echo "--- Cloning repository into $HOME_DIR ---"
cd $HOME_DIR
git clone $GIT_REPO_URL

echo "--- Setting permissions ---"
# Move the .env file into the project directory
mv $HOME_DIR/.env $PROJECT_DIR/.env
# Change the owner of the entire project directory to the ec2-user
chown -R $DEFAULT_USER:$DEFAULT_USER $PROJECT_DIR

echo "--- Building and running the application with Docker Compose... ---"
# Switch to the 'ec2-user' to run docker-compose from the correct directory
su - $DEFAULT_USER -c "cd $PROJECT_DIR && docker-compose up --build -d"

echo "--- Deployment Script Finished! ---"