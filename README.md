# Enhanced IMDb Scraper

A comprehensive movie data extraction and management system with advanced scraping capabilities, media downloading, and rich API features.

## Features

- 🎬 **Complete Movie Data**: Extract detailed information including cast, crew, media, and reviews
- 📸 **Media Management**: Download and store movie posters, stills, and trailers
- 🔍 **Advanced Search**: Date-based filtering with comprehensive search capabilities
- 🗄️ **Rich Database**: Normalized schema with proper indexing and relationships
- 🚀 **Modern API**: FastAPI with async support and comprehensive documentation
- 📊 **Analytics Dashboard**: Rich visualizations and data insights
- 🐳 **Docker Ready**: Complete containerization with development and production configs

## Quick Start

1. **Clone and setup:**
   ```bash
   git clone <repository>
   cd enhanced-imdb-scraper
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

2. **Start development environment:**
   ```bash
   docker-compose up
   ```

3. **Access the application:**
   - Frontend: http://localhost:8501
   - API Docs: http://localhost:8000/api/docs
   - MinIO Console: http://localhost:9001

## Project Structure

```
enhanced-imdb-scraper/
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── core/         # Core configuration
│   │   ├── models/       # Database and Pydantic models
│   │   ├── services/     # Business logic
│   │   └── workers/      # Background tasks
│   ├── alembic/          # Database migrations
│   └── tests/            # Test suite
├── frontend/             # Streamlit frontend
│   └── src/
│       ├── components/   # Reusable UI components
│       ├── pages/        # Application pages
│       └── services/     # API integration
├── data/                 # Data storage
│   ├── downloads/        # Downloaded media
│   ├── exports/          # Exported data
│   └── backups/          # Database backups
└── docs/                 # Documentation
```

## API Endpoints

### Movies
- `GET /api/v1/movies/` - List movies with pagination
- `GET /api/v1/movies/{id}` - Get movie details
- `POST /api/v1/movies/` - Create movie
- `PUT /api/v1/movies/{id}` - Update movie
- `DELETE /api/v1/movies/{id}` - Delete movie

### Search
- `GET /api/v1/search/movies` - Search movies
- `GET /api/v1/search/people` - Search people
- `GET /api/v1/search/advanced` - Advanced search

### Scraping
- `POST /api/v1/scraping/start` - Start scraping job
- `GET /api/v1/scraping/status/{job_id}` - Get job status
- `GET /api/v1/scraping/jobs` - List all jobs

### Media
- `GET /api/v1/media/images/{movie_id}` - Get movie images
- `GET /api/v1/media/videos/{movie_id}` - Get movie videos
- `POST /api/v1/media/download` - Download media

## Configuration

Copy `.env.example` to `.env` and configure:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/imdb_scraper

# External APIs (optional but recommended)
IPSTACK_API_KEY=your_ipstack_key
TMDB_API_KEY=your_tmdb_key

# Proxy settings (for scraping)
PROXY_HOST=your.proxy.com
PROXY_PORT=8080
PROXY_USERNAME=username
PROXY_PASSWORD=password
```

## Development

1. **Backend development:**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

2. **Frontend development:**
   ```bash
   cd frontend
   pip install -r requirements.txt
   streamlit run src/app.py
   ```

3. **Database migrations:**
   ```bash
   cd backend
   alembic revision --autogenerate -m "Description"
   alembic upgrade head
   ```

4. **Run tests:**
   ```bash
   cd backend
   pytest
   ```

## Deployment

### Production with Docker
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### Manual deployment
1. Set production environment variables
2. Build Docker images
3. Deploy with docker-compose
4. Run database migrations
5. Configure reverse proxy (nginx)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
# IMBD-Scraper
