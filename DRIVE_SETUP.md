# Google Drive API Setup Guide

To enable Google Drive backups, you need to provide a `credentials.json` file. This allows the application to authenticate securely with your Google account.

## Steps to Generate `credentials.json`

1.  **Go to Google Cloud Console**
    *   Visit: [https://console.cloud.google.com/](https://console.cloud.google.com/)
    *   Create a new project (e.g., "Relighting-Backup").

2.  **Enable Google Drive API**
    *   In the sidebar, go to **APIs & Services** > **Library**.
    *   Search for "Google Drive API".
    *   Click **Enable**.

3.  **Configure OAuth Consent Screen**
    *   Go to **APIs & Services** > **OAuth consent screen**.
    *   Choose **External** (for personal use) and click **Create**.
    *   Fill in the required App Name and Email fields.
    *   **Important:** Add your Google email as a **Test User**.

4.  **Create Credentials**
    *   Go to **APIs & Services** > **Credentials**.
    *   Click **Create Credentials** > **OAuth client ID**.
    *   Select Application Type: **Desktop app**.
    *   Click **Create**.

5.  **Download JSON**
    *   You will see a "Client ID created" popup.
    *   Click the **Download JSON** button.
    *   Rename this file to `credentials.json` and place it in the root folder of this project:
        `/root/Relighting_Dataset_Engine/credentials.json`

## Why is this needed?
Google requires secure OAuth2 authentication to access your Drive files. This file contains the keys identifying your application. The first time you run the backup, you will be asked to authorize via a link in the terminal.
