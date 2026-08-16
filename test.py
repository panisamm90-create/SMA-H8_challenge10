from fastapi import FastAPI
app = FastAPI(
    title='Smart Urban Mobility AI',
    version='1.0'
)
@app.get('/')
def root():
    return{
        'message' : 'Backend is running successfully'
    }