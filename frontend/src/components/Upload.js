import axios from "axios";
import { useState } from "react";

const Upload = () => {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("");

  const handleUpload = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      setStatus("Uploading...");
      await axios.post("http://127.0.0.1:8000/upload", formData);
      setStatus("Document uploaded successfully ✅");
    } catch (err) {
      setStatus("Upload failed ❌");
    }
  };

  return (
    <div>
      <h3>Upload Document</h3>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} />
      <button onClick={handleUpload}>Upload</button>
      <p>{status}</p>
    </div>
  );
};

export default Upload;
