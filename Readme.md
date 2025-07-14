# Simplified Twitter Clone - System Design Project

This project is a simplified implementation of a Twitter-like social media platform, built to demonstrate a scalable backend architecture using modern technologies. It focuses on core functionalities such as user authentication, tweeting, following other users, and generating user-specific timelines.

The key architectural pattern implemented is **Fan-out-on-write**, which is optimized for read-heavy social media applications. This ensures that user timelines are loaded instantly, providing a fast and seamless user experience.

## Features

-   **User Authentication:** Secure user signup and login using password hashing (bcrypt) and JWT access tokens stored in HTTP-only cookies.
-   **Tweeting:** Logged-in users can post new tweets.
-   **User Following System:** Users can find, follow, and unfollow other users.
-   **Profile Pages:** View user profiles, including their tweets, followers, and who they are following.
-   **Persistent Timelines:** A user's timeline, consisting of their own tweets and tweets from users they follow, persists across server restarts.
-   **Fan-out-on-write Timeline Generation:** Timelines are pre-computed and cached for extremely fast reads.
    -   New tweets are pushed to follower timelines in the background via a message queue.
    -   When a user is followed, their recent tweets are "backfilled" into the new follower's timeline.

## Tech Stack

| Component              | Technology                               | Purpose                                                                                                                              |
| ---------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **API Framework** | `FastAPI`                                | For building the high-performance, asynchronous REST APIs.                                                                           |
| **Database** | `PostgreSQL`                             | The primary relational database (source of truth) for storing user data, tweets, and follow relationships.                           |
| **Message Queue** | `Apache Kafka`                           | Decouples tweet creation from timeline delivery. Handles the fan-out process asynchronously.                                         |
| **Caching** | `Redis`                                  | An in-memory data store used to cache pre-computed user timelines for near-instantaneous read access.                                |
| **Containerization** | `Docker` & `Docker Compose`              | To containerize the application and all its services, ensuring a consistent and reproducible environment for development and deployment. |
| **Frontend Templating**| `Jinja2`                                 | To render server-side HTML pages for the user interface.                                                                             |

## System Design: Fan-out-on-write

This project implements a **Fan-out-on-write** architecture, a common pattern for read-heavy systems like social media feeds.

**The Concept:** Instead of calculating a user's timeline every time they request it (which is slow), we do the heavy lifting when a tweet is created (the "write"). The new tweet is immediately pushed ("fanned out") to the timeline cache of every follower. This makes reading a timeline as simple as fetching a pre-computed list from a high-speed cache.

### Message Queue (Kafka) Implementation

We use Kafka to make the fan-out process asynchronous and resilient.

1.  **Producer (The `web` service):**
    -   When a user posts a new tweet via the `/tweets` endpoint, the `web` service's first job is to save the tweet to the **PostgreSQL** database. This is the "source of truth."
    -   Immediately after saving, it creates a JSON message containing the `tweet_id` and `author_id`.
    -   This message is sent (produced) to a Kafka topic named `new_tweets`.
    -   The API then instantly returns a success response to the user, without waiting for the fan-out to complete.

2.  **Consumer (The `consumer` service):**
    -   A separate, dedicated service runs the `consumer.py` script. It continuously listens to the `new_tweets` Kafka topic.
    -   When it receives a new tweet message, it performs the **fan-out logic**:
        -   It queries the PostgreSQL database to get the list of all users who follow the tweet's author.
        -   For each follower, it pushes the new `tweet_id` to the top of their timeline list in the **Redis cache**.
        -   It also adds the tweet to the author's own timeline cache.

### Caching (Redis) Implementation

We use Redis to store the pre-computed timelines for every user.

1.  **Writing to the Cache (The `consumer` and `web` services):**
    -   The `consumer` service writes to the cache during the fan-out process described above.
    -   The `web` service writes to the cache when a user follows another user. The `/follow/{user_id}` endpoint triggers a "backfill" process, fetching the new "friend's" recent tweets and adding their IDs to the current user's timeline cache.
    -   Each user's timeline is stored as a **Redis List**, with the key `timeline:<user_id>`.

2.  **Reading from the Cache (The `web` service):**
    -   When a user visits the homepage (`/`), the application performs a single, fast operation:
    -   It fetches a list of tweet IDs from Redis using the command `LRANGE timeline:<user_id> 0 100`.
    -   It then uses this list of IDs to fetch the full tweet objects from the PostgreSQL database in one query.
    -   This two-step process (get IDs from cache, then get full objects from DB) is extremely fast and scalable.

## Project Structure

```
twitter_clone/
│
├── app/
│   ├── __init__.py
│   ├── main.py          # Main FastAPI app, homepage route
│   ├── database.py      # PostgreSQL connection setup
│   ├── cache.py         # Redis connection setup
│   ├── models.py        # SQLAlchemy database table models
│   ├── producer.py      # Kafka message producer logic
│   ├── schemas.py       # Pydantic data validation schemas
│   ├── security.py      # Password hashing & JWT authentication
│   │
│   ├── routers/
│   │   ├── tweets.py    # API routes for creating tweets
│   │   └── users.py     # API routes for users, auth, and following
│   │
│   ├── static/
│   │   └── css/         # CSS stylesheets
│   │
│   └── templates/       # Jinja2 HTML templates
│
├── consumer.py          # Kafka consumer script (fan-out worker)
├── .env                 # Environment variables (DB URL, secrets)
├── .gitignore           # Files to be ignored by Git
├── Dockerfile           # Instructions to build the application image
├── docker-compose.yml   # Defines and orchestrates all services
├── pyproject.toml       # Python project dependencies for Poetry
├── requirements.txt     # Python project dependencies for pip
└── README.md            # This file
```

## Local Development Setup

### Prerequisites

-   [Docker](https://www.docker.com/products/docker-desktop/)
-   [Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop)
-   [Poetry](https://python-poetry.org/docs/#installation) (for managing Python dependencies)

### Instructions

1.  **Clone the Repository**
    ```sh
    git clone <your-repository-url>
    cd twitter-clone
    ```

2.  **Create the Environment File**
    -   Create a file named `.env` in the project's root directory.
    -   Copy the contents of `.env.example` (or the code below) into it. You can use the default values for local development.
    ```ini
    # .env
    DATABASE_URL=postgresql://user:password@db:5432/twitter_clone_db
    SECRET_KEY=a_very_strong_and_long_secret_key_for_testing
    ALGORITHM=HS256
    ACCESS_TOKEN_EXPIRE_MINUTES=30
    REDIS_HOST=cache
    REDIS_PORT=6379
    ```

3.  **Generate the Poetry Lock File**
    -   If the `poetry.lock` file is not present, generate it:
    ```sh
    poetry lock
    ```

4.  **Build and Run the Application**
    -   Use Docker Compose to build the images and start all services.
    ```sh
    docker-compose up --build
    ```
    -   The `-d` flag can be added to run the containers in the background (`docker-compose up --build -d`).

5.  **Access the Application**
    -   Open your web browser and navigate to **http://localhost:8000**.

## Deployment to AWS EC2

This project can be deployed to an AWS EC2 instance using a setup script.

### Prerequisites

-   An AWS account.
-   Your code pushed to a GitHub repository.

### Instructions

1.  **Launch an EC2 Instance:**
    -   Go to the AWS EC2 console.
    -   Launch a new instance using an **Amazon Linux 2** or **Ubuntu** AMI.
    -   An instance type of **`t2.small`** or larger is recommended due to the memory requirements of Kafka.
    -   In the **Security Group** settings, add an **Inbound rule** to allow `Custom TCP` traffic on port `8000` from source `Anywhere-IPv4 (0.0.0.0/0)`.

2.  **Use the Deployment Script:**
    -   During the instance launch, under the **"Advanced details"** section, paste the content of the `deploy.sh` script (tailored for your chosen OS) into the **"User data"** field.
    -   **Important:** You must fill in your actual GitHub repository URL and secrets within the script before pasting it.

3.  **Access the Application:**
    -   After the instance has launched and the script has had a few minutes to run, you can access your live application at `http://<your-ec2-public-ip>:8000`.
