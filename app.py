"""Wathba patient app and separate clinician workspace. Paid Space stays paused."""
import os
import gradio as gr
import uvicorn
from wathba import llm, storage
from wathba.webapp import create_app
from wathba.review_ui import build_review_app

app=create_app()
app=gr.mount_gradio_app(app,build_review_app(),path='/physio',allowed_paths=[str(storage.root())],ssr_mode=False)

if __name__=='__main__':
    llm.preload()
    uvicorn.run(app,host=os.getenv('WATHBA_HOST','127.0.0.1' if not os.getenv('SPACE_ID') else '0.0.0.0'),port=int(os.getenv('PORT','7860')))
