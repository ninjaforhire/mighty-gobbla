from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional
import os
import shutil
import logging
from processor import process_document
from history import add_history_entry, get_history

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MightyGobbla")

app = FastAPI(title="MIGHTY GOBBLA!")

# CORS 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directory exists
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))



@app.post("/upload_files")
async def upload_files_endpoint(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        try:
            # Save temporary file
            temp_path = f".tmp/{file.filename}"
            os.makedirs(".tmp", exist_ok=True)
            
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Process the file
            processed_info = process_document(temp_path)
            
            # Generate Naming Convention (for Notion & History)
            # Format: YYMMDD-Store-Payment
            ext = os.path.splitext(file.filename)[1]
            base_new_name = f"{processed_info['date']}-{processed_info['store']}-{processed_info['payment']}"
            base_new_name = base_new_name.replace("/", "").replace(":", "")
            new_name = f"{base_new_name}{ext}"
            
            # For uploads, we can't rename the source file on the phone, 
            # but we use the correct name for Notion/History.
            processed_info['filename'] = new_name

            # Notion Check
            notion_result = None
            history_added = False
            from settings import get_setting
            if get_setting("notion_enabled"):
                from notion_integration import add_to_notion_expenses
                notion_result = add_to_notion_expenses(processed_info)
                
                # Only add to history if success
                if notion_result and notion_result.get('status') == 'success':
                     add_history_entry(new_name, processed_info, directory="Mobile Upload")
                     history_added = True
            else:
                add_history_entry(new_name, processed_info, directory="Mobile Upload")
                history_added = True
            
            results.append({
                "original": file.filename,
                "new": new_name,
                "status": "gobbled", 
                "data": processed_info,
                "notion_status": notion_result,
                "history_added": history_added
            })

        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}")
            results.append({"original": file.filename, "status": "error", "message": str(e)})

    return {"results": results}
async def process_file_path_endpoint(file_path: str = Form(...)):
    """Process a single local file in-place."""
    # Strip quotes just in case backend receives them
    file_path = file_path.strip().strip('"').strip("'")
    
    if not os.path.exists(file_path):
        return {"results": [{"original": file_path, "status": "error", "message": "File not found"}]}
    
    filename = os.path.basename(file_path)
    root = os.path.dirname(file_path)
    
    # Logic similar to folder processing
    try:
        processed_info = process_document(file_path)
        
        ext = os.path.splitext(filename)[1]
        
        base_new_name = f"{processed_info['date']}-{processed_info['store']}-{processed_info['payment']}"
        base_new_name = base_new_name.replace("/", "").replace(":", "")
        
        new_name = f"{base_new_name}{ext}"
        new_path = os.path.join(root, new_name)
        
        # Collision Handling
        counter = 1
        while os.path.exists(new_path) and new_path != file_path:
            new_name = f"{base_new_name}_{counter}{ext}"
            new_path = os.path.join(root, new_name)
            counter += 1
            
        if file_path != new_path:
            os.rename(file_path, new_path)
            logger.info(f"Renamed {file_path} -> {new_path}")
            
        # Notion Check
        notion_result = None
        history_added = False
        from settings import get_setting
        if get_setting("notion_enabled"):
            from notion_integration import add_to_notion_expenses
            processed_info['filename'] = new_name # Update to renamed filename for Notion
            notion_result = add_to_notion_expenses(processed_info)
            
            # Only add to history if success
            if notion_result and notion_result.get('status') == 'success':
                 add_history_entry(new_name, processed_info, directory=root)
                 history_added = True
        else:
            # If Notion disabled, we just log it as processed locally
            add_history_entry(new_name, processed_info, directory=root)
            history_added = True
            
        return {
            "results": [
                {
                    "original": filename, 
                    "new": new_name, 
                    "status": "gobbled",
                    "notion_status": notion_result,
                    "data": processed_info,
                    "history_added": history_added
                }
            ]
        }
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"results": [{"original": filename, "status": "error", "message": str(e)}]}

@app.post("/process_folder")
async def process_folder_endpoint(folder_path: str = Form(...)):
    # Strip quotes if present
    folder_path = folder_path.strip().strip('"').strip("'")

    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=400, detail="Directory not found")

    results = []
    # Loop files
    for root, _, files in os.walk(folder_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            # Filter extensions
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
                try:
                    processed_info = process_document(file_path)
                    
                    # Rename Logic
                    # Convention: [yymmdd]-[Store]-[Payment]
                    ext = os.path.splitext(filename)[1]
                    # Format: YYMMDD-Store-Payment
                    base_new_name = f"{processed_info['date']}-{processed_info['store']}-{processed_info['payment']}"
                    base_new_name = base_new_name.replace("/", "").replace(":", "")
                    
                    new_name = f"{base_new_name}{ext}"
                    new_path = os.path.join(root, new_name)
                    
                    # Collision Handling
                    counter = 1
                    while os.path.exists(new_path) and new_path != file_path:
                        new_name = f"{base_new_name}_{counter}{ext}"
                        new_path = os.path.join(root, new_name)
                        counter += 1

                    
                    # Rename
                    if file_path != new_path:
                        os.rename(file_path, new_path)
                        logger.info(f"Renamed {file_path} -> {new_path}")
                        
                    # Notion Check
                    notion_result = None
                    history_added = False
                    from settings import get_setting
                    if get_setting("notion_enabled"):
                        from notion_integration import add_to_notion_expenses
                        processed_info['filename'] = new_name
                        notion_result = add_to_notion_expenses(processed_info)
                        
                        if notion_result and notion_result.get('status') == 'success':
                            add_history_entry(new_name, processed_info, directory=root)
                            history_added = True
                    else:
                        add_history_entry(new_name, processed_info, directory=root)
                        history_added = True

                    results.append({
                        "original": filename, 
                        "new": new_name, 
                        "status": "gobbled",
                        "notion_status": notion_result,
                        "history_added": history_added
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to gobble {filename}: {e}")
                    results.append({"original": filename, "status": "error", "message": str(e)})
    
    return {"results": results}

@app.get("/history")
def get_history_endpoint(page: int = 1, limit: int = 10):
    return get_history(page, limit)

@app.delete("/history/{entry_id}")
def delete_history_item(entry_id: int):
    from history import delete_entry
    delete_entry(entry_id)
    return {"status": "deleted"}

@app.delete("/history")
def delete_all_history():
    from history import clear_history
    clear_history()
    return {"status": "cleared"}

# --- Settings Endpoints ---
@app.get("/settings")
def get_settings_endpoint():
    from settings import load_settings
    return load_settings()

@app.post("/notion/force_add")
async def force_add_notion(
    filename: str = Form(...),
    date: str = Form(...),
    store: str = Form(...),
    payment: str = Form(...),
    amount: float = Form(...)
):
    from notion_integration import add_to_notion_expenses
    from settings import get_setting
    
    # We construct the data and call a modified version or just "trust" it?
    # Actually, we need to modify add_to_notion to create directly, OR we just
    # ...create it directly here using logic similar to add_to_notion but without check.
    # To keep code clean, let's just use the existing function but we need to bypass check.
    # Hack: Pass a special flag in data? No, let's refactor slightly if needed.
    # Or just copy the creation logic here for simplicity.
    
    token = get_setting("notion_token")
    db_id = get_setting("notion_db_id")
    import requests
    from datetime import datetime
    
    # ISO date conversion
    try:
        dt = datetime.strptime(date, "%y%m%d")
        iso_date = dt.strftime("%Y-%m-%d")
    except:
        iso_date = datetime.now().strftime("%Y-%m-%d")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    # Updated Schema Logic
    # Parse Payment for metadata
    payment_method = "Other"
    payment_type = "Credit Card"
    last_4 = ""
    
    if "Card" in payment:
        payment_type = "Credit Card"
        if "-" in payment:
            last_4 = payment.split("-")[1]
            if last_4 == "XXXX": last_4 = ""
    elif "Check" in payment:
        payment_method = "Check"
        payment_type = "Check"
        if "-" in payment:
            last_4 = payment.split("-")[1]
    elif "Cash" in payment:
        payment_method = "Cash"
        payment_type = "Cash"
        
    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Expense Description": {"title": [{"text": {"content": filename}}]},
            "Vendor/Supplier": {"rich_text": [{"text": {"content": store}}]},
            "Date Paid": {"date": {"start": iso_date}},
            "Subtotal": {"number": amount},
            "Payment Type": {"select": {"name": payment_type}}
        }
    }
    
    if payment_method != "Other":
        payload["properties"]["Payment Method"] = {"select": {"name": payment_method}}
        
    if last_4:
        payload["properties"]["Last 4 of Card"] = {"rich_text": [{"text": {"content": last_4}}]}
    
    try:
        resp = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
        if resp.status_code == 200:
            # Success! Add to History now.
            from history import add_history_entry
            # Reconstruct details dict for history (since we don't pass 'processed_info' fully, we remake it)
            details = {
                "date": date, # Passed as yymmdd string from form
                "store": store,
                "payment": payment,
                "amount": amount
            }
            # Directory? We don't have it in form. "Force Add" is contextless. 
            # We can default to "Unknown/ForceAdd"
            add_history_entry(filename, details, directory="Force Add")
            
            return {"status": "success", "url": resp.json().get('url')}
        else:
            return {"status": "error", "message": resp.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/settings")
async def update_settings_endpoint(
    notion_enabled: bool = Form(...),
    notion_token: Optional[str] = Form(None),
    notion_db_id: Optional[str] = Form(None)
):
    from settings import set_setting, save_settings, load_settings
    
    # Load current and update
    current = load_settings()
    current["notion_enabled"] = notion_enabled
    
    # Only update credentials if explicitly provided (frontend might hide them)
    if notion_token is not None and notion_token.strip() != "":
        current["notion_token"] = notion_token
        
    if notion_db_id is not None and notion_db_id.strip() != "":
        current["notion_db_id"] = notion_db_id
    
    save_settings(current)
    return {"status": "updated"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
