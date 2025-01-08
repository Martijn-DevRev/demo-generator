# DevRev Demo Org Generator

A web application for automatically generating and populating demo organizations in DevRev. This tool creates a complete demo environment including users, accounts, product hierarchy, tickets, issues, and opportunities using AI-generated content based on your company's website.

## Features

- 🤖 AI-powered content generation based on company website
- 👥 Automatic creation of developer and customer users
- 🏢 Company account generation with associated contacts
- 🗂️ Product hierarchy creation (capabilities, features, subfeatures)
- 🎫 Support ticket generation with realistic content
- 🐛 Engineering issue creation
- 💼 Sales opportunity generation
- 🌐 Web scraping integration
- ⚙️ Configuration management (SLA, auto-reply settings)
- 📊 Progress tracking and status reporting
- 📥 Session-based log downloading

## Prerequisites

- Python 3.10 or higher
- DevRev PAT (Personal Access Token)
- OpenAI API key
- NGINX (optional example for production deployment)

## Installation

1. Clone the repository:

    git clone https://github.com/Martijn-DevRev/devrev-demo-generator.git
    cd devrev-demo-generator

2. Create and activate a virtual environment:

    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install dependencies:

    pip install -r requirements.txt

4. Copy the example environment file and fill in your credentials:

    cp config/.env.example config/.env

## Configuration

Edit `config/.env` with your settings:

    OPENAI_ORGANIZATION=your_org_id
    OPENAI_PROJECT=your_project_id
    OPENAI_API_KEY=your_api_key

## Usage

1. Start the development server:

    python main.py

2. Access the web interface at `http://localhost:5000`

3. Enter required information:
   - DevRev PAT
   - Company website URL
   - Optional: Knowledge base URL
   - Configure number of tickets/issues per part

4. Use advanced settings to:
   - Enable/disable org cleanup before generation
   - Configure auto-reply settings
   - Set up SLA configuration

Important: when cleaning up, ALL existing accounts except the creator of the org, will be deleted.

## Production Deployment

For production deployment with NGINX reverse proxy:

1. Configure NGINX (example configuration provided):

    server {
        listen 443 ssl;
        server_name your.domain.com;

        # SSL configuration
        ssl_certificate /path/to/cert.crt;
        ssl_certificate_key /path/to/key.key;

        location /demogenerator/ {
            proxy_pass http://127.0.0.1:5001/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

2. Start the application with gunicorn:

    gunicorn -w 4 -b 127.0.0.1:5001 main:app

## Project Structure

    devrev-demo-generator/
    ├── config/
    │   └── .env.example
    ├── data/
    │   └── common_input/
    │       ├── accounts.csv
    │       ├── dev_users.csv
    │       └── rev_users.csv
    ├── static/
    │   ├── images/
    │   │   └── logo.png
    │   └── js/
    │       └── main.js
    ├── templates/
    │   └── index.html
    ├── main.py
    ├── create_org.py
    ├── configuration_features.py
    ├── devrev_objects.py
    ├── GPT.py
    └── utils.py

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Authors

- Martijn Bosschaart (martijn@devrev.ai) - Initial work and maintenance

## Acknowledgments

- Based on work by Jae Hosking
