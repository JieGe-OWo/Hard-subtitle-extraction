import uvicorn

from app.config import MAX_UPLOAD_SIZE

if __name__ == '__main__':
    uvicorn.run('app.main:app', host='0.0.0.0', port=int(__import__('os').getenv('PORT', '8000')),
                workers=1, limit_max_requests=int(MAX_UPLOAD_SIZE))
