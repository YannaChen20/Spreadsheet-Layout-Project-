import React, { useState } from "react";

function App() {
  const [file, setFile] = useState(null);
  const [image, setImage] = useState(null);
  const [structure, setStructure] = useState([]);
  const [templateName, setTemplateName] = useState("");
  const [customTemplateName, setCustomTemplateName] = useState(""); // New state for custom template name
  const [fileInfo, setFileInfo] = useState(null);
  const [batchResults, setBatchResults] = useState([]);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setImage(null);
    setStructure([]);
    setFileInfo(null);
  };

  const uploadFile = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("http://127.0.0.1:8000/upload/", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    setImage(`data:image/png;base64,${data.image}`);
    setStructure(data.layout || []);
    console.log("Detected Layout:", data.layout);
    setFileInfo({ file_id: data.file_id, filename: data.filename });
  };

  const handleSaveTemplate = async () => {
    if (!fileInfo) return;
    if (!customTemplateName.trim()) {
      return alert("Please enter a custom template name");
    }
    
    const formData = new FormData();
    formData.append("file_id", fileInfo.file_id);
    formData.append("filename", fileInfo.filename);
    formData.append("custom_name", customTemplateName); // Pass custom template name
    
    const res = await fetch("http://127.0.0.1:8000/save_template/", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    alert("Template saved: " + data.template_id);
    // 自动设置当前的模板名称
    setTemplateName(data.template_id);
  };

  const handleLoadTemplate = async () => {
    if (!templateName) return alert("Please enter a template name.");
    const res = await fetch(`http://127.0.0.1:8000/load_template/${templateName}`);
    if (!res.ok) {
      alert(`Error: ${res.status} - Template not found`);
      return;
    }
    const data = await res.json();
    if (data?.layout) {
      alert("Template loaded successfully.");
    } else {
      alert("Template loaded but no layout found.");
    }
  };

  const applyTemplate = async () => {
    if (!fileInfo || !templateName) {
      if (!fileInfo) {
        return alert("Please upload a file first");
      }
      if (!templateName) {
        return alert("Please enter a template name");
      }
      return;
    }
    
    const formData = new FormData();
    formData.append("file_id", fileInfo.file_id);
    formData.append("filename", fileInfo.filename);
    formData.append("template_id", templateName);
    
    const res = await fetch("http://127.0.0.1:8000/apply_template/", {
      method: "POST",
      body: formData,
    });
    
    if (!res.ok) {
      alert(`Error: ${res.status} - Failed to apply template`);
      return;
    }
    
    const data = await res.json();
    setImage(`data:image/png;base64,${data.image}`);
    setStructure(data.layout || []);
    alert("Template applied successfully");
  };

  const handleExportCSV = async () => {
    if (!fileInfo) return;
    const formData = new FormData();
    formData.append("file_id", fileInfo.file_id);
    formData.append("filename", fileInfo.filename);
    const res = await fetch("http://127.0.0.1:8000/export_csv/", {
      method: "POST",
      body: formData,
    });
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileInfo.filename + ".csv";
    a.click();
  };

  const handleRegionClick = async (i) => {
    const label = prompt("Enter label for region", structure[i]?.annotation || "");
    if (!label || !fileInfo) return;

    const formData = new FormData();
    formData.append("file_id", fileInfo.file_id);
    formData.append("filename", fileInfo.filename);
    formData.append("block_index", i);
    formData.append("label", label);

    const res = await fetch("http://127.0.0.1:8000/annotate/", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    setStructure(data.layout || []);
    console.log("Detected Layout:", data.layout);

  };

  const handleBatchProcess = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const formData = new FormData();
    for (let f of files) {
      formData.append("file_list", f);
    }
    const res = await fetch("http://127.0.0.1:8000/batch_process/", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    setBatchResults(data.batch_results || []);
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>🧩 Mondrian Spreadsheet Layout Tool</h2>

      <input type="file" onChange={handleFileChange} />
      <button onClick={uploadFile}>Upload & Detect</button>

      <div style={{ marginTop: 10 }}>
        {/* New input field for custom template name */}
        <input
          placeholder="Enter custom template name"
          value={customTemplateName}
          onChange={(e) => setCustomTemplateName(e.target.value)}
          style={{ marginRight: '10px' }}
        />
        <button onClick={handleSaveTemplate}>Save Template</button>
      </div>

      <div style={{ marginTop: 10 }}>
        <input
          placeholder="Template name or ID to load"
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value)}
        />
        <button onClick={handleLoadTemplate}>Load Template</button>
        {fileInfo && <button onClick={applyTemplate}>Apply Template to Current File</button>}
      </div>

      <div style={{ marginTop: 10 }}>
        <button onClick={handleExportCSV}>Export CSV</button>
      </div>

      <div style={{ marginTop: 20 }}>
        <h4>📦 Batch Process Files</h4>
        <input type="file" multiple onChange={handleBatchProcess} />
        {batchResults.length > 0 && (
          <ul>
            {batchResults.map((r, i) => (
              <li key={i}>
                {r.filename} ➜ {r.matched_template_id || "No match"}
              </li>
            ))}
          </ul>
        )}
      </div>

      {image && (
        <div style={{ marginTop: 20 }}>
          <h4>🧱 Blocks (Click to Annotate)</h4>
          <ul>
            {structure.map((region, i) => (
              <li
                key={i}
                onClick={() => handleRegionClick(i)}
                style={{ cursor: "pointer", marginBottom: "5px" }}
              >
                🧩 [{region.top},{region.left}] →{" "}
                <strong>{region.annotation || "Unlabeled"}</strong>
                <div style={{ fontSize: "0.8em", marginTop: 4 }}>
                  <pre>{JSON.stringify(region.text, null, 2)}</pre>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default App;