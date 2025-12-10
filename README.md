# Multi-Illumination Indoor Scene Dataset Suite 🏠💡

A complete automation toolkit for building high-quality indoor scene datasets with diverse lighting conditions. This project integrates an image scraper, a dataset management web interface, and a robust ComfyUI backend for batch processing.

## 🌟 Features

*   **Integrated Scraper**: Automatically collect potential source images from the web.
*   **Dataset Curator App**: A clean local web interface to review buffer images, approve them for the dataset, or discard them.
*   **ComfyUI Automation**: Connects to your local ComfyUI instance to automatically generate **25 distinct lighting variations** for every scene (Time of Day, Temperature, Stylized).
*   **Gallery Viewer**: Review your generated results side-by-side.
*   **Cloud Backup**: One-click compression and upload of your dataset to Google Drive.

## 🛠️ Prerequisites

1.  **Python 3.10+** installed.
2.  **ComfyUI** running locally (default: `http://127.0.0.1:8188`).
    *   You must have a working Flux/ControlNet workflow capable of relighting.
3.  **Google Cloud Project** (Optional, for backup):
    *   Enable Drive API.
    *   Download OAuth 2.0 `credentials.json`.

## 📦 Installation

1.  Clone this repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

### 1. ComfyUI Workflow
*   Export your ComfyUI workflow in **API Format**.
    *   Go to ComfyUI Settings -> Enable "Dev Mode Options".
    *   Click "Save (API Format)" on the menu.
*   Save the file as `workflow_api.json` in this project folder.

### 2. Node Mapping
*   Open `processor.py`.
*   Update the constants at the top to match your specific Node IDs from the JSON:
    ```python
    NODE_ID_LOAD_IMAGE = "10"  # Your Load Image Node ID
    NODE_ID_PROMPT_TEXT = "6"  # Your Positive Prompt Node ID
    ```

### 3. Google Drive (Optional)
*   Place your `credentials.json` file in the project root.

## 🚀 Usage

Start the web application:

```bash
python3 app.py
```

Open your browser to **http://127.0.0.1:5000**.

### Workflow Steps:

1.  **Buffer Tab**:
    *   Enter a count and click **Scrape**.
    *   Review downloaded images. Click **Approve** to move them to the dataset or **Discard** to remove them.
2.  **Input Dataset Tab**:
    *   View your approved queue.
    *   Click **Start Processing** to send jobs to ComfyUI.
    *   *Note: Ensure ComfyUI makes progress in its console.*
3.  **Gallery Tab**:
    *   Browse the processed scenes. Each scene folder contains the original (`light0`) and 25 variations.
4.  **Export Tab**:
    *   Click **Start Backup** to zip the `output_dataset` and upload it to your Google Drive.

## 💡 Lighting Categories implemented

The system automatically prompts for:
*   **Natural**: Morning, Golden Hour, Overcast, God Rays...
*   **Artificial**: Tungsten, Fluorescent, Candle, Neon...
*   **Stylized**: Cyberpunk, Noir, Underwater, Horror...

## 📄 License
MIT License. Feel free to use and modify for your research or creative projects.
