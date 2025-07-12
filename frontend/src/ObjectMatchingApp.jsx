import React, { useState, useEffect } from 'react';
import { Upload, Search, Database, BarChart3, FileText, Image, Loader2, CheckCircle, XCircle, AlertCircle, RefreshCw, Settings } from 'lucide-react';

const ObjectMatchingApp = () => {
  const [activeTab, setActiveTab] = useState('database');
  const [apiUrl, setApiUrl] = useState('http://object-matching-backend.eastus.azurecontainer.io:8000');
  const [stats, setStats] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [queryResults, setQueryResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('unknown');

  // Database loading state
  const [dbLoading, setDbLoading] = useState(false);
  const [dbParams, setDbParams] = useState({
    confidence_threshold: 0.5,
    max_workers: 4,
    target_class: 'clipper',
    model_path: 'runs/train/yolo11_custom/weights/best.pt'
  });

  // Query state - UPDATED with min_similarity
  const [queryParams, setQueryParams] = useState({
    confidence_threshold: 0.5,
    top_k: 10,
    object_class: '',
    target_class: 'clipper',
    model_path: 'best.pt',
    min_similarity: 0.5  // Added min_similarity parameter
  });

  // Test connection to API
  const testConnection = async () => {
    setConnectionStatus('testing');
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

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

  // Enhanced fetch with error handling
  const fetchWithErrorHandling = async (url, options = {}) => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (err) {
      if (err.name === 'AbortError') {
        throw new Error('Request timeout');
      }
      throw err;
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const data = await fetchWithErrorHandling(`${apiUrl}/stats`);
      setStats(data);
    } catch (err) {
      console.error('Error fetching stats:', err);
      setStats(null);
    }
  };

  // Fetch tasks
  const fetchTasks = async () => {
    try {
      const data = await fetchWithErrorHandling(`${apiUrl}/tasks`);
      setTasks(data.tasks || []);
    } catch (err) {
      console.error('Error fetching tasks:', err);
      setTasks([]);
    }
  };

  // Load database from files
const loadDatabaseFromFiles = async (files) => {
  setDbLoading(true);
  setError(null);

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
      alert(`Database loading started from ${files.length} files. Task ID: ${data.task_id}`);
      fetchTasks();
    } else {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to start database loading from files');
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
        alert(`Database loading started from ZIP. Task ID: ${data.task_id}`);
        fetchTasks();
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to start database loading from ZIP');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setDbLoading(false);
    }
  };

  // Query object - UPDATED to include min_similarity
  const queryObject = async (file) => {
    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('query_image', file);
      formData.append('confidence_threshold', queryParams.confidence_threshold.toString());
      formData.append('top_k', queryParams.top_k.toString());
      formData.append('object_class', queryParams.object_class);
      formData.append('target_class', queryParams.target_class);
      formData.append('model_path', queryParams.model_path);
      formData.append('min_similarity', queryParams.min_similarity.toString()); // Added min_similarity

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
        throw new Error(errorData.detail || 'Failed to query object');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Clear database
  const clearDatabase = async () => {
    if (window.confirm('Are you sure you want to clear the database?')) {
      try {
        const response = await fetch(`${apiUrl}/database/clear`, {
          method: 'DELETE'
        });
        if (response.ok) {
          setError(null);
          alert('Database cleared successfully');
          fetchStats();
        } else {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Failed to clear database');
        }
      } catch (err) {
        setError(err.message);
      }
    }
  };

  useEffect(() => {
    const initializeApp = async () => {
      const isConnected = await testConnection();
      if (isConnected) {
        fetchStats();
        fetchTasks();
      }
    };

    initializeApp();
  }, [apiUrl]);

  // Auto-refresh when connected
  useEffect(() => {
    if (connectionStatus === 'connected') {
      const interval = setInterval(() => {
        fetchStats();
        fetchTasks();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [connectionStatus, apiUrl]);

  const ConnectionStatusIndicator = () => {
    const statusConfig = {
      unknown: { color: 'text-gray-500', bg: 'bg-gray-100', text: 'Unknown' },
      testing: { color: 'text-blue-500', bg: 'bg-blue-100', text: 'Testing...' },
      connected: { color: 'text-green-500', bg: 'bg-green-100', text: 'Connected' },
      error: { color: 'text-red-500', bg: 'bg-red-100', text: 'Disconnected' }
    };

    const config = statusConfig[connectionStatus];

    return (
      <div className={`flex items-center gap-2 px-3 py-1 rounded-full ${config.bg}`}>
        <div className={`w-2 h-2 rounded-full ${config.color.replace('text-', 'bg-')}`} />
        <span className={`text-sm font-medium ${config.color}`}>{config.text}</span>
      </div>
    );
  };

  const StatusIcon = ({ status }) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'running':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      default:
        return <AlertCircle className="w-4 h-4 text-yellow-500" />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-800 mb-2">Object Matching System</h1>
              <p className="text-gray-600">Clipper Matcher (YOLO + DINOv2)</p>
            </div>
            <ConnectionStatusIndicator />
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              placeholder="API URL (e.g., http://localhost:8000)"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md flex-1"
            />
            <button
              onClick={testConnection}
              disabled={connectionStatus === 'testing'}
              className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {connectionStatus === 'testing' ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              Test Connection
            </button>
          </div>

          {/* Connection troubleshooting help */}
          {connectionStatus === 'error' && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
              <h4 className="font-medium text-yellow-800 mb-2">Connection Issues?</h4>
              <ul className="text-sm text-yellow-700 space-y-1">
                <li>• Check if the API server is running</li>
                <li>• Verify the URL is correct (note the port in your URL)</li>
                <li>• Ensure CORS is enabled on the API server</li>
                <li>• Try using the full URL: http://object-matching-backend.eastus.azurecontainer.io:8000</li>
              </ul>
            </div>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-center gap-2">
              <XCircle className="w-5 h-5 text-red-500" />
              <span className="text-red-700">{error}</span>
            </div>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="bg-white rounded-lg shadow-lg mb-6">
          <div className="flex border-b border-gray-200">
            {[
              { id: 'database', label: 'Database', icon: Database },
              { id: 'query', label: 'Query', icon: Search },
              { id: 'stats', label: 'Statistics', icon: BarChart3 },
              { id: 'tasks', label: 'Tasks', icon: FileText }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex items-center gap-2 px-6 py-3 font-medium transition-colors ${
                  activeTab === id
                    ? 'border-b-2 border-blue-500 text-blue-600'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>

          <div className="p-6">
            {/* Database Tab */}
            {activeTab === 'database' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Confidence Threshold
                      </label>
                      <input
                          type="number"
                          step="0.1"
                          min="0"
                          max="1"
                          value={dbParams.confidence_threshold}
                          onChange={(e) => setDbParams({...dbParams, confidence_threshold: parseFloat(e.target.value)})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Max Workers
                      </label>
                      <input
                          type="number"
                          min="1"
                          max="16"
                          value={dbParams.max_workers}
                          onChange={(e) => setDbParams({...dbParams, max_workers: parseInt(e.target.value)})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Target Class
                      </label>
                      <input
                          type="text"
                          value={dbParams.target_class}
                          onChange={(e) => setDbParams({...dbParams, target_class: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Model Path
                      </label>
                      <input
                          type="text"
                          value={dbParams.model_path}
                          onChange={(e) => setDbParams({...dbParams, model_path: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      />
                    </div>

                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <h4 className="font-medium text-gray-900">Feature Extractor</h4>
                      <p className="text-sm text-gray-600">{stats?.feature_extractor || 'N/A'}</p>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <h4 className="font-medium text-gray-900">Feature Dimension</h4>
                      <p className="text-sm text-gray-600">{stats?.feature_dimension || 'N/A'}</p>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <h4 className="font-medium text-gray-900">Device</h4>
                      <p className="text-sm text-gray-600">{stats?.device || 'N/A'}</p>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <h4 className="font-medium text-gray-900">Patch Features</h4>
                      <p className="text-sm text-gray-600">{stats?.patch_features ? 'Enabled' : 'Disabled'}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                      <Upload className="w-8 h-8 mx-auto mb-4 text-gray-400"/>
                      <h3 className="text-lg font-medium mb-2">Load from Files</h3>
                      <input
                          type="file"
                          accept="image/*"
                          multiple
                          className="w-full px-3 py-2 border border-gray-300 rounded-md mb-4"
                          id="files-input"
                      />
                      <button
                          onClick={() => {
                            const files = document.getElementById('files-input').files;
                            if (files && files.length > 0) loadDatabaseFromFiles(files);
                          }}
                          disabled={dbLoading || connectionStatus !== 'connected'}
                          className="w-full px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors"
                      >
                        {dbLoading ? <Loader2 className="w-4 h-4 animate-spin mx-auto"/> : 'Load Database'}
                      </button>
                    </div>

                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                      <Upload className="w-8 h-8 mx-auto mb-4 text-gray-400"/>
                      <h3 className="text-lg font-medium mb-2">Load from ZIP</h3>
                      <input
                          type="file"
                          accept=".zip"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md mb-4"
                          id="zip-input"
                      />
                      <button
                          onClick={() => {
                            const file = document.getElementById('zip-input').files[0];
                            if (file) loadDatabaseFromZip(file);
                          }}
                          disabled={dbLoading || connectionStatus !== 'connected'}
                          className="w-full px-4 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 disabled:opacity-50 transition-colors"
                      >
                        {dbLoading ? <Loader2 className="w-4 h-4 animate-spin mx-auto"/> : 'Load from ZIP'}
                      </button>
                    </div>
                  </div>

                  <div className="flex justify-center">
                    <button
                        onClick={clearDatabase}
                        disabled={connectionStatus !== 'connected'}
                        className="px-6 py-2 bg-red-500 text-white rounded-md hover:bg-red-600 disabled:opacity-50 transition-colors"
                    >
                      Clear Database
                    </button>
                  </div>
                </div>
            )}

            {/* Query Tab - UPDATED with min_similarity field */}
            {activeTab === 'query' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                      Confidence Threshold
                      </label>
                      <input
                          type="number"
                          step="0.1"
                          min="0"
                          max="1"
                          value={queryParams.confidence_threshold}
                          onChange={(e) => setQueryParams({
                            ...queryParams,
                            confidence_threshold: parseFloat(e.target.value)
                          })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Top K Results
                      </label>
                      <input
                          type="number"
                          min="1"
                          max="100"
                      value={queryParams.top_k}
                      onChange={(e) => setQueryParams({...queryParams, top_k: parseInt(e.target.value)})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Minimum Similarity
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="1"
                      value={queryParams.min_similarity}
                      onChange={(e) => setQueryParams({...queryParams, min_similarity: parseFloat(e.target.value)})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                </div>

                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                  <Image className="w-8 h-8 mx-auto mb-4 text-gray-400" />
                  <h3 className="text-lg font-medium mb-2">Query Object</h3>
                  <input
                    type="file"
                    accept="image/*"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md mb-4"
                    id="query-input"
                  />
                  <button
                    onClick={() => {
                      const file = document.getElementById('query-input').files[0];
                      if (file) queryObject(file);
                    }}
                    disabled={loading || connectionStatus !== 'connected'}
                    className="w-full px-4 py-2 bg-purple-500 text-white rounded-md hover:bg-purple-600 disabled:opacity-50 transition-colors"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'Search Similar Objects'}
                  </button>
                </div>

                {/* Query Results */}
                {queryResults.length > 0 && (
                  <div>
                    <h3 className="text-lg font-medium mb-4">Query Results</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {queryResults.map((result, index) => (
                        <div key={index} className="border border-gray-200 rounded-lg p-4">
                          <div className="mb-2">
                            <img
                              src={`${apiUrl}/database/objects/${result.object_id}/image`}
                              alt={`Object ${result.object_id}`}
                              className="w-full h-32 object-cover rounded-md mb-2"
                              onError={(e) => {
                                e.target.style.display = 'none';
                              }}
                            />
                          </div>
                          <div className="text-sm space-y-1">
                            <div><strong>Score:</strong> {result.similarity_score?.toFixed(3) || 'N/A'}</div>
                            <div><strong>Class:</strong> {result.object_class || 'N/A'}</div>
                            <div><strong>Confidence:</strong> {result.confidence?.toFixed(3) || 'N/A'}</div>
                            <div><strong>Feature Dim:</strong> {result.feature_dim || 0}</div>
                            <div><strong>File:</strong> {result.original_filename || 'N/A'}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Stats Tab */}
            {activeTab === 'stats' && (
              <div className="space-y-6">
                {stats ? (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="bg-blue-50 p-4 rounded-lg">
                        <h3 className="font-medium text-blue-900">Total Images</h3>
                        <p className="text-2xl font-bold text-blue-600">{stats.database_stats?.total_images || 0}</p>
                      </div>
                      <div className="bg-green-50 p-4 rounded-lg">
                        <h3 className="font-medium text-green-900">Total Objects</h3>
                        <p className="text-2xl font-bold text-green-600">{stats.database_stats?.total_objects || 0}</p>
                      </div>
                      <div className="bg-purple-50 p-4 rounded-lg">
                        <h3 className="font-medium text-purple-900">Avg Feature Dim</h3>
                        <p className="text-2xl font-bold text-purple-600">{stats.database_stats?.avg_feature_dim?.toFixed(1) || '0.0'}</p>
                      </div>
                    </div>

                    {stats.database_stats?.class_counts && (
                        <div>
                          <h3 className="text-lg font-medium mb-4">Class Distribution</h3>
                          <div className="space-y-2">
                          {Object.entries(stats.database_stats.class_counts).map(([cls, count]) => (
                            <div key={cls} className="flex justify-between items-center bg-gray-50 p-2 rounded">
                              <span className="font-medium">{cls}</span>
                              <span className="text-gray-600">{count}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    {connectionStatus === 'connected' ? 'Loading statistics...' : 'Connect to API to view statistics'}
                  </div>
                )}
              </div>
            )}

            {/* Tasks Tab */}
            {activeTab === 'tasks' && (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-lg font-medium">Background Tasks</h3>
                  <button
                    onClick={fetchTasks}
                    disabled={connectionStatus !== 'connected'}
                    className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors"
                  >
                    Refresh
                  </button>
                </div>

                {tasks.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    {connectionStatus === 'connected' ? 'No background tasks found' : 'Connect to API to view tasks'}
                  </div>
                ) : (
                  <div className="space-y-2">
                    {tasks.map((taskId) => (
                      <TaskItem key={taskId} taskId={taskId} apiUrl={apiUrl} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Task Item Component
const TaskItem = ({ taskId, apiUrl }) => {
  const [taskDetails, setTaskDetails] = useState(null);

  useEffect(() => {
    const fetchTaskDetails = async () => {
      try {
        const response = await fetch(`${apiUrl}/tasks/${taskId}`);
        if (response.ok) {
          const data = await response.json();
          setTaskDetails(data);
        }
      } catch (err) {
        console.error('Error fetching task details:', err);
      }
    };

    fetchTaskDetails();
    const interval = setInterval(fetchTaskDetails, 2000);
    return () => clearInterval(interval);
  }, [taskId, apiUrl]);

  if (!taskDetails) return null;

  const StatusIcon = ({ status }) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'running':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      default:
        return <AlertCircle className="w-4 h-4 text-yellow-500" />;
    }
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusIcon status={taskDetails.status} />
          <span className="font-medium">{taskId}</span>
        </div>
        <span className="text-sm text-gray-500">{taskDetails.status}</span>
      </div>
      {taskDetails.error && (
        <div className="mt-2 text-sm text-red-600">{taskDetails.error}</div>
      )}
      {taskDetails.result && (
        <div className="mt-2 text-sm text-green-600">
          Task completed successfully
        </div>
      )}
    </div>
  );
};

export default ObjectMatchingApp;