use crate::wfo::{OptunaWfoEvaluator, WfoRunOptions};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::sync::Mutex;

fn py_runtime_error(error: impl std::fmt::Display) -> PyErr {
    PyRuntimeError::new_err(error.to_string())
}

#[pyclass(name = "WfoEvaluator")]
pub struct PyWfoEvaluator {
    inner: Mutex<OptunaWfoEvaluator>,
}

#[pymethods]
impl PyWfoEvaluator {
    #[new]
    fn new(options_json: &str) -> PyResult<Self> {
        let options =
            serde_json::from_str::<WfoRunOptions>(options_json).map_err(py_runtime_error)?;
        let inner = OptunaWfoEvaluator::new(options).map_err(py_runtime_error)?;
        Ok(Self {
            inner: Mutex::new(inner),
        })
    }

    fn run_id(&self) -> PyResult<String> {
        let inner = self.inner.lock().map_err(py_runtime_error)?;
        Ok(inner.run_id().to_string())
    }

    fn run_dir(&self) -> PyResult<String> {
        let inner = self.inner.lock().map_err(py_runtime_error)?;
        Ok(inner.run_dir().display().to_string())
    }

    fn config_json(&self) -> PyResult<String> {
        let inner = self.inner.lock().map_err(py_runtime_error)?;
        serde_json::to_string(inner.config()).map_err(py_runtime_error)
    }

    fn groups_json(&self) -> PyResult<String> {
        let inner = self.inner.lock().map_err(py_runtime_error)?;
        serde_json::to_string(&inner.groups()).map_err(py_runtime_error)
    }

    fn folds_json(&self) -> PyResult<String> {
        let inner = self.inner.lock().map_err(py_runtime_error)?;
        serde_json::to_string(inner.folds()).map_err(py_runtime_error)
    }

    fn start_group(&self, py: Python<'_>, indicator: String, timeframe: String) -> PyResult<()> {
        py.detach(move || {
            let mut inner = self.inner.lock().map_err(py_runtime_error)?;
            inner
                .start_group(&indicator, &timeframe)
                .map_err(py_runtime_error)
        })
    }

    fn start_fold_group(
        &self,
        py: Python<'_>,
        indicator: String,
        timeframe: String,
        fold_index: usize,
        study_name: String,
        seed: u64,
        trials_requested: usize,
    ) -> PyResult<()> {
        py.detach(move || {
            let mut inner = self.inner.lock().map_err(py_runtime_error)?;
            inner
                .start_fold_group(
                    &indicator,
                    &timeframe,
                    fold_index,
                    &study_name,
                    seed,
                    trials_requested,
                )
                .map_err(py_runtime_error)
        })
    }

    fn evaluate_batch_json(
        &self,
        py: Python<'_>,
        indicator: String,
        timeframe: String,
        batch_json: String,
    ) -> PyResult<String> {
        py.detach(move || {
            let mut inner = self.inner.lock().map_err(py_runtime_error)?;
            let results = inner
                .evaluate_batch_json(&indicator, &timeframe, &batch_json)
                .map_err(py_runtime_error)?;
            serde_json::to_string(&results).map_err(py_runtime_error)
        })
    }

    fn evaluate_fold_batch_json(
        &self,
        py: Python<'_>,
        indicator: String,
        timeframe: String,
        fold_index: usize,
        batch_json: String,
    ) -> PyResult<String> {
        py.detach(move || {
            let mut inner = self.inner.lock().map_err(py_runtime_error)?;
            let results = inner
                .evaluate_fold_batch_json(&indicator, &timeframe, fold_index, &batch_json)
                .map_err(py_runtime_error)?;
            serde_json::to_string(&results).map_err(py_runtime_error)
        })
    }

    fn complete_fold_group(
        &self,
        py: Python<'_>,
        indicator: String,
        timeframe: String,
        fold_index: usize,
    ) -> PyResult<()> {
        py.detach(move || {
            let mut inner = self.inner.lock().map_err(py_runtime_error)?;
            inner
                .complete_fold_group(&indicator, &timeframe, fold_index)
                .map_err(py_runtime_error)
        })
    }

    fn complete_group(&self, py: Python<'_>, indicator: String, timeframe: String) -> PyResult<()> {
        py.detach(move || {
            let mut inner = self.inner.lock().map_err(py_runtime_error)?;
            inner
                .complete_group(&indicator, &timeframe)
                .map_err(py_runtime_error)
        })
    }

    fn finalize(&self, py: Python<'_>) -> PyResult<String> {
        py.detach(move || {
            let mut inner = self.inner.lock().map_err(py_runtime_error)?;
            let run_dir = inner.finalize().map_err(py_runtime_error)?;
            Ok(run_dir.display().to_string())
        })
    }
}

#[pymodule]
#[pyo3(name = "_rust")]
pub fn rust_trend_optuna_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyWfoEvaluator>()?;
    Ok(())
}
