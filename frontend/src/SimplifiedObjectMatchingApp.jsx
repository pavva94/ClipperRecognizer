import React, { useState, useEffect } from 'react';
import { Upload, Search, Loader2, CheckCircle, XCircle, AlertCircle, Settings } from 'lucide-react';

const SimplifiedObjectMatchingApp = () => {
  const [apiUrl] = useState('http://object-matching-backend.eastus.azurecontainer.io:8000');
  const [connectionStatus, setConnectionStatus] = useState('unknown');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [queryResults, setQueryResults] = useState([]);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Database loading state
  const [dbLoading, setDbLoading] = useState(false);
  const [dbSuccess, setDbSuccess] = useState(false);

  // Simplified parameters - hidden from user but configurable
  const [dbParams] = useState({
    confidence_threshold: 0.5,
    max_workers: 4,
    target_class: 'clipper',
    model_path: 'runs/train/yolo11_custom/weights/best.pt'
  });

  const [queryParams, setQueryParams] = useState({
    confidence_threshold: 0.5,
    top_k: 10,
    object_class: '',
    target_class: 'clipper',
    model_path: 'best.pt',
    min_similarity: 0.5
  });

  // Test connection to API
  const testConnection = async () => {
    setConnectionStatus('testing');
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(`${apiUrl}/health`, {
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
        }
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        setConnectionStatus('connected');
        setError(null);
        return true;
      } else {
        setConnectionStatus('error');
        setError(`API responded with status: ${response.status}`);
        return false;
      }
    } catch (err) {
      setConnectionStatus('error');
      if (err.name === 'AbortError') {
        setError('Connection timeout - API may be down or unreachable');
      } else {
        setError(`Connection failed: ${err.message}`);
      }
      return false;
    }
  };

  // Load database from files
  const loadDatabaseFromFiles = async (files) => {
    setDbLoading(true);
    setError(null);
    setDbSuccess(false);

    try {
      const formData = new FormData();

      // Append all files
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
      }

      // Append parameters
      formData.append('confidence_threshold', dbParams.confidence_threshold.toString());
      formData.append('max_workers', dbParams.max_workers.toString());
      formData.append('target_class', dbParams.target_class);
      formData.append('model_path', dbParams.model_path);

      const response = await fetch(`${apiUrl}/database/load-from-files`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        setError(null);
        setDbSuccess(true);
        // Auto-hide success message after 5 seconds
        setTimeout(() => setDbSuccess(false), 5000);
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to load database from files');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setDbLoading(false);
    }
  };

  // Load database from ZIP
  const loadDatabaseFromZip = async (file) => {
    setDbLoading(true);
    setError(null);
    setDbSuccess(false);

    try {
      const formData = new FormData();
      formData.append('zip_file', file);
      formData.append('confidence_threshold', dbParams.confidence_threshold.toString());
      formData.append('max_workers', dbParams.max_workers.toString());
      formData.append('target_class', dbParams.target_class);
      formData.append('model_path', dbParams.model_path);

      const response = await fetch(`${apiUrl}/database/load-from-zip`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        setError(null);
        setDbSuccess(true);
        // Auto-hide success message after 5 seconds
        setTimeout(() => setDbSuccess(false), 5000);
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to load database from ZIP');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setDbLoading(false);
    }
  };

  // Query object
  const queryObject = async (file) => {
    setLoading(true);
    setError(null);
    setQueryResults([]);

    try {
      const formData = new FormData();
      formData.append('query_image', file);
      formData.append('confidence_threshold', queryParams.confidence_threshold.toString());
      formData.append('top_k', queryParams.top_k.toString());
      formData.append('object_class', queryParams.object_class);
      formData.append('target_class', queryParams.target_class);
      formData.append('model_path', queryParams.model_path);
      formData.append('min_similarity', queryParams.min_similarity.toString());

      const response = await fetch(`${apiUrl}/query`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        setQueryResults(data);
        setError(null);
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to search for similar objects');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    testConnection();
  }, []);

  const ConnectionStatusBadge = () => {
    const statusConfig = {
      unknown: { color: 'text-gray-600', bg: 'bg-gray-100', text: 'Connecting...' },
      testing: { color: 'text-blue-600', bg: 'bg-blue-100', text: 'Testing...' },
      connected: { color: 'text-green-600', bg: 'bg-green-100', text: 'Connected' },
      error: { color: 'text-red-600', bg: 'bg-red-100', text: 'Disconnected' }
    };

    const config = statusConfig[connectionStatus];

    return (
      <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${config.bg} ${config.color}`}>
        <div className={`w-2 h-2 rounded-full ${config.color.replace('text-', 'bg-')}`} />
        {config.text}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">Object Matching</h1>
          <p className="text-gray-600 mb-4">Find similar objects in your image collection</p>
          <ConnectionStatusBadge />
        </div>

        {/* Error Alert */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center gap-2">
            <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <span className="text-red-700">{error}</span>
          </div>
        )}

        {/* Success Alert */}
        {dbSuccess && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6 flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
            <span className="text-green-700">Database loaded successfully!</span>
          </div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Database Loading Section */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <Upload className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-800">Load Database</h2>
                <p className="text-gray-600 text-sm">Upload images to build your searchable database</p>
              </div>
            </div>

            {/* Upload Multiple Files */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Upload Multiple Images
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors">
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  className="w-full"
                  id="files-input"
                  disabled={dbLoading || connectionStatus !== 'connected'}
                />
                <p className="text-sm text-gray-500 mt-2">Select multiple image files</p>
              </div>
              <button
                onClick={() => {
                  const files = document.getElementById('files-input').files;
                  if (files && files.length > 0) loadDatabaseFromFiles(files);
                }}
                disabled={dbLoading || connectionStatus !== 'connected'}
                className="w-full mt-3 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {dbLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Load Files
                  </>
                )}
              </button>
            </div>

            {/* Upload ZIP */}
            <div className="border-t pt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Or Upload ZIP File
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-green-400 transition-colors">
                <input
                  type="file"
                  accept=".zip"
                  className="w-full"
                  id="zip-input"
                  disabled={dbLoading || connectionStatus !== 'connected'}
                />
                <p className="text-sm text-gray-500 mt-2">Select a ZIP file containing images</p>
              </div>
              <button
                onClick={() => {
                  const file = document.getElementById('zip-input').files[0];
                  if (file) loadDatabaseFromZip(file);
                }}
                disabled={dbLoading || connectionStatus !== 'connected'}
                className="w-full mt-3 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {dbLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Load ZIP
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Search Section */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                <Search className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-800">Search Similar</h2>
                <p className="text-gray-600 text-sm">Find objects similar to your uploaded image</p>
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Upload Image to Search
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-purple-400 transition-colors">
                <input
                  type="file"
                  accept="image/*"
                  className="w-full"
                  id="query-input"
                  disabled={loading || connectionStatus !== 'connected'}
                />
                <p className="text-sm text-gray-500 mt-2">Select an image to find similar objects</p>
              </div>
              <button
                onClick={() => {
                  const file = document.getElementById('query-input').files[0];
                  if (file) queryObject(file);
                }}
                disabled={loading || connectionStatus !== 'connected'}
                className="w-full mt-3 px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    Search
                  </>
                )}
              </button>
            </div>

            {/* Advanced Settings Toggle */}
            <div className="border-t pt-4">
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
              >
                <Settings className="w-4 h-4" />
                {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
              </button>

              {showAdvanced && (
                <div className="mt-4 space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Maximum Results
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="50"
                      value={queryParams.top_k}
                      onChange={(e) => setQueryParams({...queryParams, top_k: parseInt(e.target.value)})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Minimum Similarity (0-1)
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="1"
                      value={queryParams.min_similarity}
                      onChange={(e) => setQueryParams({...queryParams, min_similarity: parseFloat(e.target.value)})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Results Section */}
        {queryResults.length > 0 && (
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-xl font-semibold text-gray-800 mb-4">
              Search Results ({queryResults.length} found)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {queryResults.map((result, index) => (
                <div key={index} className="border border-gray-200 rounded-lg p-3 hover:shadow-md transition-shadow">
                  <div className="aspect-square mb-3 bg-gray-100 rounded-lg overflow-hidden">
                    <img
                      src={`${apiUrl}/database/objects/${result.object_id}/image`}
                      alt={`Similar object ${index + 1}`}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTIxIDEyQzIxIDEyIDIxIDEyIDIxIDEyQzIxIDEyIDIxIDEyIDIxIDEyWiIgZmlsbD0iIzk5OTk5OSIvPgo8L3N2Zz4K';
                      }}
                    />
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-700">Similarity</span>
                      <span className="text-sm font-semibold text-green-600">
                        {(result.similarity_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Confidence</span>
                      <span className="text-sm text-gray-800">
                        {(result.confidence * 100).toFixed(1)}%
                      </span>
                    </div>
                    {result.original_filename && (
                      <div className="text-xs text-gray-500 truncate" title={result.original_filename}>
                        {result.original_filename}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Connection Help */}
        {connectionStatus === 'error' && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mt-6">
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle className="w-5 h-5 text-yellow-600" />
              <h4 className="font-medium text-yellow-800">Connection Issues</h4>
            </div>
            <ul className="text-sm text-yellow-700 space-y-1">
              <li>• Make sure the API server is running</li>
              <li>• Check your internet connection</li>
              <li>• The system will automatically reconnect when available</li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default SimplifiedObjectMatchingApp;