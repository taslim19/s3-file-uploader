## Cloud File Storage (Mini Google Drive)

FastAPI-based cloud file storage service that mimics a simplified Google Drive.
It integrates with AWS S3 for file blobs, uses SQLite for metadata, and exposes
REST + HTML endpoints for a BSc CS-ready mini project.

### Features
- User registration & JWT login.
- File upload/download via AWS S3 with per-user quotas.
- Expiring shareable links using presigned URLs.
- Admin dashboard to inspect users, files, and storage usage.
- Metrics tracking: upload counts, total bytes, per-file download counts.

### Local Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # then edit keys described below
uvicorn app.main:app --reload
```

### Configuration
Set these keys in `.env` (or environment variables):

```
DATABASE_URL=sqlite:///./cloud_drive.db
SECRET_KEY=super-secret-change-me
ACCESS_TOKEN_EXPIRE_MINUTES=60
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-south-1
S3_BUCKET_NAME=mini-drive-bucket
```

### Tech Stack
- FastAPI + Pydantic for REST + HTML.
- SQLAlchemy ORM on SQLite.
- boto3 for S3 operations & presigned URLs.
- Passlib + python-jose for password hashing + JWT auth.
- Starlette templates for a minimal dashboard/admin UI.

### Project Layout
```
app/
  __init__.py
  config.py
  database.py
  models.py
  schemas.py
  auth.py
  services/
    storage.py
    stats.py
  routers/
    users.py
    files.py
    admin.py
templates/
  auth_login.html
  dashboard.html
  admin.html
static/
  styles.css
```

### Testing the Flow
1. Register a user through `/auth/register`.
2. Log in via `/auth/login` to obtain a JWT or use the HTML login form.
3. Use `/files/upload` (multipart) to push files into S3; metadata lands in SQLite.
4. Generate expiring links via `/files/{file_id}/share?minutes=30`.
5. Inspect aggregate stats at `/admin` (requires admin role).

### Notes
- For classroom demos without AWS, point `S3_ENDPOINT_URL` at LocalStack or MinIO.
- The code keeps things framework-light so it is easy to present and explain.

