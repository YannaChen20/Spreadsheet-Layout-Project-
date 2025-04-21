from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import uvicorn, os, io, shutil, json
from typing import List
import uuid
import base64
import matplotlib.pyplot as plt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
EXPORT_DIR = "exports"
TEMPLATE_DIR = "templates"
LAYOUT_DIR = "layouts"  

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs(LAYOUT_DIR, exist_ok=True)  

templates = {}
template_name_map = {}  


def read_excel(file_path):
    return pd.read_excel(file_path, header=None)

def detect_layout(df, file_id=None, filename=None):
    layout_path = None
    if file_id and filename:
        layout_path = os.path.join(LAYOUT_DIR, f"{file_id}_{filename}_layout.json")
        if os.path.exists(layout_path):
            with open(layout_path, "r", encoding="utf-8") as f:
                return json.load(f)
    
    data = df.fillna("nan").astype(str).values.tolist()
    max_len = max(len(row) for row in data)
    for row in data:
        while len(row) < max_len:
            row.append("nan")

    blocks = []
    current_block = []
    start_row = 0

    def save_block(start, end, block_rows):
        if not block_rows:
            return
        blocks.append({
            "label": len(blocks),
            "top": start,
            "bottom": end - 1,
            "left": 0,
            "right": max_len - 1,
            "text": block_rows
        })

    for i, row in enumerate(data):
        if all(cell.strip() == "" or cell == "nan" for cell in row):
            save_block(start_row, i, current_block)
            current_block = []
            start_row = i + 1
        else:
            current_block.append(row)

    save_block(start_row, len(data), current_block)
    
    # 保存布局到文件
    if layout_path:
        with open(layout_path, "w", encoding="utf-8") as f:
            json.dump(blocks, f)
            
    return blocks

def save_layout(file_id, filename, layout):
    layout_path = os.path.join(LAYOUT_DIR, f"{file_id}_{filename}_layout.json")
    with open(layout_path, "w", encoding="utf-8") as f:
        json.dump(layout, f)

def load_layout(file_id, filename):
    layout_path = os.path.join(LAYOUT_DIR, f"{file_id}_{filename}_layout.json")
    if os.path.exists(layout_path):
        with open(layout_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_template(template_id, filename, layout, custom_name=None):
    path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")
    data = {
        "template_id": template_id,
        "filename": filename,
        "structure": layout,  
        "layout": layout,     
        "custom_name": custom_name  
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    
    if custom_name:
        name_map_path = os.path.join(TEMPLATE_DIR, "name_map.json")
        name_map = {}
        if os.path.exists(name_map_path):
            with open(name_map_path, "r", encoding="utf-8") as f:
                try:
                    name_map = json.load(f)
                except:
                    name_map = {}
        
        name_map[custom_name] = template_id
        with open(name_map_path, "w", encoding="utf-8") as f:
            json.dump(name_map, f)

def load_templates():
    global templates, template_name_map
    templates.clear()
    template_name_map.clear()
    
    name_map_path = os.path.join(TEMPLATE_DIR, "name_map.json")
    if os.path.exists(name_map_path):
        with open(name_map_path, "r", encoding="utf-8") as f:
            try:
                template_name_map = json.load(f)
            except:
                template_name_map = {}
    
    for file in os.listdir(TEMPLATE_DIR):
        if file.endswith(".json") and file != "name_map.json":
            with open(os.path.join(TEMPLATE_DIR, file), "r", encoding="utf-8") as f:
                data = json.load(f)
                templates[file[:-5]] = data

def compare_layout(layout1, layout2):
    return len(layout1) == len(layout2)

def plot_layout_image(df, layout):
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(np.ones(df.shape), cmap='gray', alpha=0)
    for block in layout:
        top, left, bottom, right = block["top"], block["left"], block["bottom"], block["right"]
        rect = plt.Rectangle((left, top), right-left+1, bottom-top+1,
                             edgecolor='red', facecolor='none', linewidth=2)
        ax.add_patch(rect)
        ax.text(left, top, str(block["label"]), color="blue", fontsize=8)
        
        if "annotation" in block:
            ax.text(left, bottom + 1, f"Annotation: {block['annotation']}", 
                   color="green", fontsize=8, verticalalignment='top')
    
    ax.set_xticks([])
    ax.set_yticks([])
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()

def get_template_id(name_or_id):
    template_path = os.path.join(TEMPLATE_DIR, f"{name_or_id}.json")
    if os.path.exists(template_path):
        return name_or_id
    
    load_templates()  
    if name_or_id in template_name_map:
        return template_name_map[name_or_id]
    
    return None


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    df = read_excel(file_path)
    layout = detect_layout(df, file_id, file.filename)
    save_layout(file_id, file.filename, layout) 
    image_base64 = plot_layout_image(df, layout)
    return {
        "file_id": file_id,
        "filename": file.filename,
        "layout": layout,
        "image": image_base64
    }

@app.post("/save_template/")
async def save_as_template(
    file_id: str = Form(...), 
    filename: str = Form(...),
    custom_name: str = Form(None)  
):
    layout = load_layout(file_id, filename)  
    if not layout:
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
        if not os.path.exists(file_path):
            return JSONResponse(content={"error": "File not found"}, status_code=404)
        df = read_excel(file_path)
        layout = detect_layout(df)
    
    if custom_name:
        load_templates() 
        if custom_name in template_name_map:
            return JSONResponse(
                content={"error": f"Template name '{custom_name}' already exists"}, 
                status_code=400
            )
    
    template_id = str(uuid.uuid4())
    save_template(template_id, filename, layout, custom_name)
    
    display_id = custom_name if custom_name else template_id
    return {"template_id": display_id}

@app.get("/load_template/{template_id}")
async def load_template(template_id: str):
    actual_id = get_template_id(template_id)
    if not actual_id:
        return JSONResponse(content={"error": "Template not found"}, status_code=404)
    
    path = os.path.join(TEMPLATE_DIR, f"{actual_id}.json")
    if not os.path.exists(path):
        return JSONResponse(content={"error": "Template not found"}, status_code=404)
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

@app.post("/apply_template/")
async def apply_template(
    file_id: str = Form(...),
    filename: str = Form(...),
    template_id: str = Form(...)
):
    actual_id = get_template_id(template_id)
    if not actual_id:
        return JSONResponse(content={"error": "Template not found"}, status_code=404)
    
    template_path = os.path.join(TEMPLATE_DIR, f"{actual_id}.json")
    if not os.path.exists(template_path):
        return JSONResponse(content={"error": "Template not found"}, status_code=404)
    
    with open(template_path, "r", encoding="utf-8") as f:
        template_data = json.load(f)
    
    template_layout = None
    if "layout" in template_data:
        template_layout = template_data["layout"]
    elif "structure" in template_data:
        template_layout = template_data["structure"]
    
    if not template_layout:
        return JSONResponse(content={"error": "Invalid template format"}, status_code=400)
    
    layout = load_layout(file_id, filename)
    if not layout:
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
        if not os.path.exists(file_path):
            return JSONResponse(content={"error": "File not found"}, status_code=404)
        df = read_excel(file_path)
        layout = detect_layout(df)
    
    if len(layout) == len(template_layout):
        for i, template_block in enumerate(template_layout):
            if "annotation" in template_block:
                layout[i]["annotation"] = template_block["annotation"]
    else:
        return JSONResponse(content={"error": "Template does not match file layout"}, status_code=400)
    
    save_layout(file_id, filename, layout)
    
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
    df = read_excel(file_path)
    image_base64 = plot_layout_image(df, layout)
    
    return {
        "file_id": file_id,
        "filename": filename,
        "layout": layout,
        "image": image_base64
    }

@app.post("/annotate/")
async def annotate_region(
    file_id: str = Form(...),
    filename: str = Form(...),
    block_index: int = Form(...),
    label: str = Form(...)
):
    layout = load_layout(file_id, filename)
    if not layout:
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
        if not os.path.exists(file_path):
            return JSONResponse(content={"error": "File not found"}, status_code=404)
        df = read_excel(file_path)
        layout = detect_layout(df)
    
    if 0 <= block_index < len(layout):
        layout[block_index]["annotation"] = label
        
    save_layout(file_id, filename, layout)
    
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
    df = read_excel(file_path)
    image_base64 = plot_layout_image(df, layout)
    
    return {
        "file_id": file_id,
        "filename": filename,
        "layout": layout,
        "image": image_base64
    }

@app.post("/export_csv/")
async def export_csv(file_id: str = Form(...), filename: str = Form(...)):
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
    if not os.path.exists(file_path):
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    
    # Read the original Excel file
    df = read_excel(file_path)
    
    # Load the layout with annotations
    layout = load_layout(file_id, filename)
    if layout:
        # Create a new DataFrame to store the annotated data
        annotated_df = pd.DataFrame()
        
        # Add a new column for annotations
        df_with_annotations = df.copy()
        df_with_annotations['annotation'] = ""
        
        # Apply annotations from layout
        for block in layout:
            if "annotation" in block and block["annotation"]:
                # Get row ranges from the block
                top, bottom = block["top"], block["bottom"]
                
                # Set the annotation for these rows
                df_with_annotations.loc[top:bottom, 'annotation'] = block["annotation"]
        
        # Use the annotated DataFrame for export
        export_path = os.path.join(EXPORT_DIR, f"{file_id}_{filename}.csv")
        df_with_annotations.to_csv(export_path, index=False)
    else:
        # If no layout information found, export the original DataFrame
        export_path = os.path.join(EXPORT_DIR, f"{file_id}_{filename}.csv")
        df.to_csv(export_path, index=False, header=False)
    
    return FileResponse(export_path, media_type='text/csv', filename=filename + ".csv")
@app.post("/batch_process/")
async def batch_process(file_list: List[UploadFile] = File(...)):
    load_templates()
    results = []
    for file in file_list:
        file_id = str(uuid.uuid4())
        save_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        try:
            df = read_excel(save_path)
            layout = detect_layout(df)
            save_layout(file_id, file.filename, layout)
            
            matched_id = None
            matched_name = None
            for template_id, template_data in templates.items():
                template_layout = template_data.get("layout") or template_data.get("structure", [])
                if compare_layout(layout, template_layout):
                    matched_id = template_id
                    matched_name = template_data.get("custom_name")
                    for i, (block, template_block) in enumerate(zip(layout, template_layout)):
                        if "annotation" in template_block:
                            layout[i]["annotation"] = template_block["annotation"]
                    save_layout(file_id, file.filename, layout)
                    break
            
            display_id = matched_name if matched_name else matched_id
            results.append({
                "filename": file.filename,
                "matched_template_id": display_id
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "error": str(e)
            })
    return {"batch_results": results}