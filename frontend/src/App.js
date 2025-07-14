import React, { useState } from 'react';
import SimplifiedObjectMatchingApp from './SimplifiedObjectMatchingApp';
import ObjectMatchingApp from './ObjectMatchingApp';
import { Settings, ArrowLeft } from 'lucide-react';
import './App.css';

function App() {
  const [currentView, setCurrentView] = useState('simple'); // 'simple' or 'advanced'

  return (
    <div className="App">
      {/* View Toggle Button */}
      <div className="fixed top-4 right-4 z-10">
        <button
          onClick={() => setCurrentView(currentView === 'simple' ? 'advanced' : 'simple')}
          className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200"
        >
          {currentView === 'simple' ? (
            <>
              <Settings className="w-4 h-4" />
              Advanced Mode
            </>
          ) : (
            <>
              <ArrowLeft className="w-4 h-4" />
              Simple Mode
            </>
          )}
        </button>
      </div>

      {/* Render the appropriate component */}
      {currentView === 'simple' ? (
        <SimplifiedObjectMatchingApp />
      ) : (
        <ObjectMatchingApp />
      )}
    </div>
  );
}

export default App;