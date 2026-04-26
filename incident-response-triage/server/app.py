import uvicorn
from server.main import app

def main():
    """Main entry point for the server."""
    uvicorn.run("server.main:app", host="0.0.0.0", port=7860, reload=False)

if __name__ == "__main__":
    main()