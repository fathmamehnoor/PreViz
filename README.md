# PreViz — FIBO-Powered AI Previsualization for Blender

**PreViz** is a Blender add-on that transforms cinematic text into physically rigged 3D scenes using Bria’s FIBO model and its JSON-native structured prompting. It enables directors, filmmakers, and 3D artists to rapidly previsualize shots by converting natural language into structured scene state. Cameras, lighting, backgrounds, and foreground elements are generated and controlled through a JSON-native, agentic workflow rather than one-off image generation.

PreViz is designed for speed, control, and iteration, bridging the gap between generative AI and real production workflows.

## Features

- **Script-to-Scene**: Paste your screenplay or shot description, and PreViz automatically configures:
  - **Camera**: Sets lens focal length (e.g., "wide shot" -> 24mm) and position (e.g., "low angle").
  - **Lighting**: Sets sun position and shadow softness based on descriptions (e.g., "golden hour", "harsh noon").
- **AI Background Generation**: automatically generates high-quality EXR backplates using the **Bria AI API** based on your scene description and sets them as the world background.
- **Foregrounds on Demand**: Request specific 2D foreground elements (e.g., "burning car", "fallen tree") which are generated, cut out (background removed), and placed as 3D cards in the scene.
- **Director's Refinement**: "Talk" to your scene to make adjustments. Type "make it warmer" or "switch to a close-up", and the scene updates contextually.
- **Export to Set**: Export technical camera and lighting data (angles, heights, lens info) to a JSON file for real-world production crews.
- **Shadow Catcher**: Automatically creates a shadow catcher plane so 3D objects sit realistically on the 2D background.

---

## Prerequisites

- **Blender 2.80** or higher (Tested on 4.x).
- **Bria AI API Key**: You need an API key from [Bria AI](https://bria.ai/) to power the image generation features.

---

## Installation

### 1. Install Blender

PreViz is a Blender add-on, so Blender must be installed first.

Download Blender from the official site:
[Blender](https://www.blender.org/download/)

Install Blender 4.x (recommended and tested)

Launch Blender once to ensure it initializes its configuration folders

### 2. Clone the Repository into Blender’s Add-ons Directory

PreViz must be placed inside Blender’s add-on folder so it can be detected automatically.

**Linux**
```sh
cd ~/.config/blender/4.0/scripts/addons
git clone https://github.com/fathmamehnoor/PreViz.git
```

**macOS**
```sh
cd ~/Library/Application\ Support/Blender/4.0/scripts/addons
git clone https://github.com/fathmamehnoor/PreViz.git
```

**Windows**
```sh
cd "$env:APPDATA\Blender Foundation\Blender\4.0\scripts\addons"
git clone https://github.com/fathmamehnoor/PreViz.git
```
Replace 4.0 with your installed Blender version if needed.

### 3. Install Project Dependencies
This add-on requires external Python libraries (`requests`, `python-dotenv`). You must install these into Blender's bundled Python environment.

First, change into the add-on directory:
```sh
cd PreViz
```
Then install the dependencies using Blender’s Python executable.
**Linux / macOS:**
In your terminal run:
```bash
# Locate your Blender python executable (example path)
# /path/to/blender/3.x/python/bin/python3.10

# run pip install
/path/to/blender/python/bin/python3.10 -m pip install -r requirements.txt
```

**Windows:**
Open PowerShell as Administrator:
```powershell
# Locate your Blender python executable (example path)
# C:\Program Files\Blender Foundation\Blender 4.0\4.0\python\bin\python.exe

# run pip install
& "C:\Program Files\Blender Foundation\Blender 4.0\4.0\python\bin\python.exe" -m pip install -r requirements.txt
```


### 4. Configure API Key
1. Rename `.env.example` (if provided) to `.env` in the project root.
2. Open `.env` and add your Bria API Key:
   ```env
   BRIA_API_KEY=your_actual_api_key_here
   ```

### 5. Install Add-on in Blender
1. Open Blender.
2. Go to **Edit > Preferences > Add-ons**.
3. Click **Install...** and select the `__init__.py` file (or the zipped folder of the project).
4. Enable the add-on by checking the box next to **PreViz**.

---

## 🚀 Usage

find the **PreViz** panel in the **3D Viewport > Sidebar (N) > PreViz tab**.

### 1. Generating a Scene
1. **Paste Script**: Copy text from your script and click **Paste Clipboard** or type directly into the text box.
   > *Example: "EXT. DESERT HIGHWAY - DAY. Wide shot of a lonely road stretching to the horizon. Heat haze shimmers. High noon lighting."*
2. Click **Generate Scene**.
3. The add-on will:
   - Parse the text.
   - Set up the camera and sun.
   - Generate and download a background image.
   - Switch the viewport to **Rendered** mode.

### 2. Refining the Scene
Not happy with the result? Use the **Director's Refinement** box.
1. Type a command like *"make it sunset"* or *"move camera lower"*.
2. Click **Refine Scene**.
3. The AI updates the existing parameters without resetting everything.

### 3. Adding Foreground Elements
1. In the **Add Foreground Element** section, describe an object.
   > *Example: "rusty stop sign"*
2. Click the **+** button.
3. The object will be generated, background removed, and placed as a 2D card in front of the camera.

### 4. Exporting Data
1. Once your scene is perfect, click **Export to Set**.
2. Save the `.json` file. It contains precise measurements for your cinematographer and gaffer.

---

## Project Structure

- **`__init__.py`**: Main entry point, UI panel, and operator registration.
- **`director.py`**: Handles Blender 3D operations (Camera, Lights, Objects).
- **`cinematographer.py`**: Handles Image Generation and Background Removal APIs.
- **`scene_parser.py`**: NLP logic to convert text to scene parameters.

---

## License
[MIT License](LICENSE)
