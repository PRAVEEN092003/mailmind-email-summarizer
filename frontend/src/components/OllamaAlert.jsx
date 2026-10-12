import React from 'react';

/**
 * OllamaAlert — shown on the Summarize page when Ollama is unavailable or model is missing.
 * Silent when health is null (still loading) or when everything is ready.
 */
export default function OllamaAlert({ health }) {
  if (!health) return null;

  const isConnected = health?.ollama_status === 'connected';
  const hasModel = Boolean(health?.model_available);

  if (isConnected && hasModel) return null;

  if (!isConnected) {
    return (
      <div className="alert-banner alert-error" role="alert" aria-live="polite">
        <span className="alert-icon" aria-hidden="true">🔴</span>
        <div className="alert-body">
          <div className="alert-title">AI Service Offline</div>
          <div className="alert-desc">
            The AI service is currently unreachable. Summarization is temporarily unavailable.
          </div>
        </div>
      </div>
    );
  }

  if (!hasModel) {
    return (
      <div className="alert-banner alert-warning" role="alert" aria-live="polite">
        <span className="alert-icon" aria-hidden="true">⚠️</span>
        <div className="alert-body">
          <div className="alert-title">AI Model Unavailable</div>
          <div className="alert-desc">
            The AI summarization engine is not ready. Please ensure the service is running.
          </div>
        </div>
      </div>
    );
  }

  return null;
}
