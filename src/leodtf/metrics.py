"""
Metrics for LEO-DTF
-------------------
Computes RMSE, MAE, and other metrics for evaluation.
"""

import numpy as np


def rmse(predictions, targets):
    """
    Compute Root Mean Square Error.

    Parameters
    ----------
    predictions : array-like
        Predicted values
    targets : array-like
        Ground truth values

    Returns
    -------
    rmse_val : float
        Root mean square error
    """
    predictions = np.asarray(predictions)
    targets = np.asarray(targets)
    return np.sqrt(np.mean((predictions - targets) ** 2))


def mae(predictions, targets):
    """
    Compute Mean Absolute Error.

    Parameters
    ----------
    predictions : array-like
        Predicted values
    targets : array-like
        Ground truth values

    Returns
    -------
    mae_val : float
        Mean absolute error
    """
    predictions = np.asarray(predictions)
    targets = np.asarray(targets)
    return np.mean(np.abs(predictions - targets))


def mape(predictions, targets):
    """
    Compute Mean Absolute Percentage Error.

    Parameters
    ----------
    predictions : array-like
        Predicted values
    targets : array-like
        Ground truth values

    Returns
    -------
    mape_val : float
        Mean absolute percentage error (in %)
    """
    predictions = np.asarray(predictions)
    targets = np.asarray(targets)
    # Avoid division by zero
    mask = targets != 0
    if not np.any(mask):
        return np.nan
    return np.mean(np.abs((predictions[mask] - targets[mask]) / targets[mask])) * 100


if __name__ == "__main__":
    # Example usage (for testing)
    pass