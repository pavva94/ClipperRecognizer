import React, { useState, useEffect } from 'react';
import { Upload, Search, Database, BarChart3, FileText, Image, Loader2, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

const ObjectMatchingApp = () => {
  const [activeTab, setActiveTab] = useState('database');
  const [apiUrl, setApiUrl] = useState('http://object-matching-backend.eastus.azurecontainer.io/:8000');
  const [stats, setStats] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [queryResults, setQueryResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Database loading state
  const [dbLoading, setDbLoading] = useState(false);
  const [dbParams, setDbParams] = useState({
    confidence_threshold: 0.5,
    max_workers: 4,
    target_class: 'clipper',
    model_path: 'runs/train/yolo11_custom/weights/best.pt'
  });

  // Query state
  const [queryParams, setQueryParams] = useState({
    confidence_threshold: 0.5,
    top_k: 10,
    object_class: '',
    target_class: 'clipper',
    model_path: 'best.pt'
  });

  // Fetch stats
  const fetchStats = async () => {
    try {
      const response = await fetch(`${apiUrl}/stats`);
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  // Fetch tasks
  const fetchTasks = async () => {
    try {
      const response = await fetch(`${apiUrl}/tasks`);
      if (response.ok) {
        const data = await response.json();
        setTasks(data.tasks);
      }
    } catch (err) {
      console.error('Error fetching tasks:', err);
    }
  };

  // Load database from directory
  const loadDatabaseFromDirectory = async (directory) => {
    setDbLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('images_directory', directory);
      formData.append('confidence_threshold', dbParams.confidence_threshold);
      formData.append('max_workers', dbParams.max_workers);
      formData.append('target_class', dbParams.target_class);
      formData.append('model_path', dbParams.model_path);

      const response = await fetch(`${apiUrl}/database/load-from-directory`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        alert(`Database loading started. Task ID: ${data.task_id}`);
        fetchTasks();
      } else {
        throw new Error('Failed to start database loading');
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
      formData.append('confidence_threshold', dbParams.confidence_threshold);
      formData.append('max_workers', dbParams.max_workers);
      formData.append('target_class', dbParams.target_class);
      formData.append('model_path', dbParams.model_path);

      const response = await fetch(`${apiUrl}/database/load-from-zip`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        alert(`Database loading started from ZIP. Task ID: ${data.task_id}`);
        fetchTasks();
      } else {
        throw new Error('Failed to start database loading from ZIP');
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

    try {
      const formData = new FormData();
      formData.append('query_image', file);
      formData.append('confidence_threshold', queryParams.confidence_threshold);
      formData.append('top_k', queryParams.top_k);
      formData.append('object_class', queryParams.object_class);
      formData.append('target_class', queryParams.target_class);
      formData.append('model_path', queryParams.model_path);

      const response = await fetch(`${apiUrl}/query`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        setQueryResults(data);
      } else {
        throw new Error('Failed to query object');
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
          alert('Database cleared successfully');
          fetchStats();
        }
      } catch (err) {
        setError(err.message);
      }
    }
  };

  useEffect(() => {
    fetchStats();
    fetchTasks();
    const interval = setInterval(() => {
      fetchStats();
      fetchTasks();
    }, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [apiUrl]);

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
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Object Matching System</h1>
          <p className="text-gray-600">Clipper Matcher (YOLO + DINOv2)</p>

          <div className="mt-4 flex gap-2">
            <input
              type="text"
              placeholder="API URL"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md flex-1"
            />
            <button
              onClick={fetchStats}
              className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
            >
              Test Connection
            </button>
          </div>
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

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                    <Upload className="w-8 h-8 mx-auto mb-4 text-gray-400" />
                    <h3 className="text-lg font-medium mb-2">Load from Directory</h3>
                    <input
                      type="text"
                      placeholder="Directory path"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md mb-4"
                      id="directory-input"
                    />
                    <button
                      onClick={() => {
                        const dir = document.getElementById('directory-input').value;
                        if (dir) loadDatabaseFromDirectory(dir);
                      }}
                      disabled={dbLoading}
                      className="w-full px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors"
                    >
                      {dbLoading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'Load Database'}
                    </button>
                  </div>

                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                    <Upload className="w-8 h-8 mx-auto mb-4 text-gray-400" />
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
                      disabled={dbLoading}
                      className="w-full px-4 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 disabled:opacity-50 transition-colors"
                    >
                      {dbLoading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'Load from ZIP'}
                    </button>
                  </div>
                </div>

                <div className="flex justify-center">
                  <button
                    onClick={clearDatabase}
                    className="px-6 py-2 bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors"
                  >
                    Clear Database
                  </button>
                </div>
              </div>
            )}

            {/* Query Tab */}
            {activeTab === 'query' && (
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
                      value={queryParams.confidence_threshold}
                      onChange={(e) => setQueryParams({...queryParams, confidence_threshold: parseFloat(e.target.value)})}
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
                    disabled={loading}
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
                            />
                          </div>
                          <div className="text-sm space-y-1">
                            <div><strong>Score:</strong> {result.normalized_score.toFixed(3)}</div>
                            <div><strong>Class:</strong> {result.object_class}</div>
                            <div><strong>Confidence:</strong> {result.confidence.toFixed(3)}</div>
                            <div><strong>Matches:</strong> {result.matches_count}</div>
                            <div><strong>Keypoints:</strong> {result.keypoints_count}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Stats Tab */}
            {activeTab === 'stats' && stats && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <h3 className="font-medium text-blue-900">Total Images</h3>
                    <p className="text-2xl font-bold text-blue-600">{stats.database_stats.total_images}</p>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg">
                    <h3 className="font-medium text-green-900">Total Objects</h3>
                    <p className="text-2xl font-bold text-green-600">{stats.database_stats.total_objects}</p>
                  </div>
                  <div className="bg-purple-50 p-4 rounded-lg">
                    <h3 className="font-medium text-purple-900">Avg Keypoints</h3>
                    <p className="text-2xl font-bold text-purple-600">{stats.database_stats.avg_keypoints.toFixed(1)}</p>
                  </div>
                </div>

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
              </div>
            )}

            {/* Tasks Tab */}
            {activeTab === 'tasks' && (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-lg font-medium">Background Tasks</h3>
                  <button
                    onClick={fetchTasks}
                    className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
                  >
                    Refresh
                  </button>
                </div>

                {tasks.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No background tasks found
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

export default ObjectMatchingApp;