"""
Tests for language cross-compilers.
"""

import pytest
from slate_core.languages.haas_script import HaasScriptCrossCompiler
from slate_core.languages.pine_script import PineScriptCrossCompiler


class TestHaasScriptCompiler:
    """Tests for HaasScript cross-compiler."""

    def setup_method(self):
        self.compiler = HaasScriptCrossCompiler()

    def test_python_to_haasscript_basic(self):
        """Test basic Python to HaasScript conversion."""
        python_code = """
prices = get_close_prices()
if prices[0] > 50000:
    go_long()
"""
        haas_code = self.compiler.python_to_haasscript(python_code)

        assert "ClosePrices()" in haas_code
        assert "DoLong" in haas_code
        assert "IndexArray" in haas_code

    def test_array_index_translation_python_to_haas(self):
        """Test critical array index translation from Python to HaasScript."""
        # Python: array[0] → HaasScript: IndexArray(array, 1)
        python_code = "price = prices[0]"
        haas_code = self.compiler.python_to_haasscript(python_code)

        assert "IndexArray(prices, 1)" in haas_code

    def test_array_index_translation_haas_to_python(self):
        """Test critical array index translation from HaasScript to Python."""
        # HaasScript: IndexArray(array, 1) → Python: array[0]
        haas_code = "price = IndexArray(prices, 1)"
        python_code = self.compiler.haasscript_to_python(haas_code)

        assert "prices[0]" in python_code

    def test_validate_haasscript(self):
        """Test HaasScript validation."""
        valid_code = """
local prices = ClosePrices()
local rsi = RSI(prices, 14)
if rsi.Value < 30 then
    DoLong()
end
"""
        result = self.compiler.validate_haasscript(valid_code)
        assert result['valid'] is True

    def test_invalid_array_index(self):
        """Test detection of invalid array indices in HaasScript."""
        # HaasScript uses 1-based indexing, so array[0] is invalid
        invalid_code = "local price = prices[0]"
        result = self.compiler.validate_haasscript(invalid_code)
        assert result['valid'] is False
        assert any("1-based" in e for e in result['errors'])

    def test_analyze_array_usage(self):
        """Test array usage analysis."""
        python_code = "price = prices[5]\nvolume = volumes[10]"
        analysis = self.compiler.analyze_array_usage(python_code, 'python_to_haas')

        assert len(analysis) == 2
        assert analysis[0]['original_index'] == '5'
        assert analysis[0]['translated_index'] == '6'


class TestPineScriptCompiler:
    """Tests for Pine Script cross-compiler."""

    def setup_method(self):
        self.compiler = PineScriptCrossCompiler()

    def test_python_to_pine_script(self):
        """Test Python to Pine Script conversion."""
        python_code = "rsi = rsi(close, 14)"
        pine_code = self.compiler.python_to_pine_script(python_code)

        assert "ta.rsi" in pine_code
        assert "@version=5" in pine_code

    def test_pine_script_to_python(self):
        """Test Pine Script to Python conversion."""
        pine_code = "rsi = ta.rsi(close, 14)"
        python_code = self.compiler.pine_script_to_python(pine_code)

        assert "rsi(" in python_code

    def test_validate_pine_script(self):
        """Test Pine Script validation."""
        valid_code = """
//@version=5
strategy("Test")
if ta.rsi(close, 14) < 30
    strategy.entry("Long", strategy.long)
"""
        result = self.compiler.validate_pine_script(valid_code)
        assert result['valid'] is True

    def test_missing_version_directive(self):
        """Test detection of missing version directive."""
        invalid_code = "strategy('Test')"
        result = self.compiler.validate_pine_script(invalid_code)
        assert result['valid'] is False
        assert any("@version" in e for e in result['errors'])
