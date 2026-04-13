"""
HaasScript Cross-Compiler

Provides bidirectional translation between Python (SLATE) and HaasScript v2.0.
Handles the critical 1-based array indexing difference between the languages.

HaasScript Language Facts:
- Lua-based scripting language for HaasOnline Trade Server
- 774 commands across 6 domains (Technical Analysis: 157, Trading: 140, Helpers: 121, Enumerations: 197, Data: 63, Advanced: 97)
- Uses 1-based array indexing (first element at index 1)
- Array indexing: array[1] gets first element, array[n] gets nth element
- IndexArray(array, n) is also used for array access
- Paper trading only - NO LIVE TRADING
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HaasScriptCommand:
    """Represents a HaasScript command definition."""
    name: str
    domain: str
    parameters: List[str]
    return_type: str
    description: str


class HaasScriptCrossCompiler:
    """
    Bidirectional Python ↔ HaasScript compiler.

    Critical: Handles 1-based array indexing translation between languages.
    """

    # HaasScript command registry (sample - full registry would include all 774 commands)
    COMMANDS = {
        # Price Data Commands
        'ClosePrices': HaasScriptCommand('ClosePrices', 'data', ['interval', 'fullCandles', 'market', 'hlcStyle'], 'HaasNumberCollection', 'Get close prices'),
        'HighPrices': HaasScriptCommand('HighPrices', 'data', ['interval', 'fullCandles', 'market', 'hlcStyle'], 'HaasNumberCollection', 'Get high prices'),
        'LowPrices': HaasScriptCommand('LowPrices', 'data', ['interval', 'fullCandles', 'market', 'hlcStyle'], 'HaasNumberCollection', 'Get low prices'),
        'OpenPrices': HaasScriptCommand('OpenPrices', 'data', ['interval', 'fullCandles', 'market', 'hlcStyle'], 'HaasNumberCollection', 'Get open prices'),
        'Volume': HaasScriptCommand('Volume', 'data', ['interval', 'fullCandles', 'market'], 'HaasNumberCollection', 'Get volume data'),
        'CurrentPrice': HaasScriptCommand('CurrentPrice', 'data', ['market'], 'HaasNumberCollection', 'Get current price data'),

        # Technical Analysis Commands
        'RSI': HaasScriptCommand('RSI', 'technical_analysis', ['prices', 'period'], 'HaasNumberCollection', 'Relative Strength Index'),
        'SMA': HaasScriptCommand('SMA', 'technical_analysis', ['prices', 'period'], 'HaasNumberCollection', 'Simple Moving Average'),
        'EMA': HaasScriptCommand('EMA', 'technical_analysis', ['prices', 'period'], 'HaasNumberCollection', 'Exponential Moving Average'),
        'MACD': HaasScriptCommand('MACD', 'technical_analysis', ['prices', 'fastPeriod', 'slowPeriod', 'signalPeriod'], 'HaasNumberCollection', 'MACD Indicator'),
        'BB': HaasScriptCommand('BB', 'technical_analysis', ['prices', 'period', 'deviation'], 'HaasNumberCollection', 'Bollinger Bands'),
        'ADX': HaasScriptCommand('ADX', 'technical_analysis', ['highPrices', 'lowPrices', 'closePrices', 'period'], 'HaasNumberCollection', 'Average Directional Index'),

        # Trading Commands
        'DoLong': HaasScriptCommand('DoLong', 'trading', ['note', 'count'], 'void', 'Enter long position'),
        'DoShort': HaasScriptCommand('DoShort', 'trading', ['note', 'count'], 'void', 'Enter short position'),
        'DoExitPosition': HaasScriptCommand('DoExitPosition', 'trading', ['note', 'count'], 'void', 'Exit position'),
        'DoSignal': HaasScriptCommand('DoSignal', 'trading', ['signal', 'note'], 'void', 'Execute signal'),
        'StopLoss': HaasScriptCommand('StopLoss', 'trading', ['percentage', 'positionId'], 'void', 'Set stop loss'),
        'TakeProfit': HaasScriptCommand('TakeProfit', 'trading', ['percentage', 'positionId'], 'void', 'Set take profit'),

        # Array/Helper Commands
        'IndexArray': HaasScriptCommand('IndexArray', 'helpers', ['array', 'index'], 'number', 'Access array element by index'),
        'LenArray': HaasScriptCommand('LenArray', 'helpers', ['array'], 'number', 'Get array length'),
        'SliceArray': HaasScriptCommand('SliceArray', 'helpers', ['array', 'startIndex', 'endIndex'], 'array', 'Get array slice'),
        'Add': HaasScriptCommand('Add', 'helpers', ['input1', 'input2'], 'number', 'Add two numbers'),
        'Sub': HaasScriptCommand('Sub', 'helpers', ['input1', 'input2'], 'number', 'Subtract two numbers'),
        'Mul': HaasScriptCommand('Mul', 'helpers', ['input1', 'input2'], 'number', 'Multiply two numbers'),
        'Div': HaasScriptCommand('Div', 'helpers', ['input1', 'input2'], 'number', 'Divide two numbers'),
        'Abs': HaasScriptCommand('Abs', 'helpers', ['input'], 'number', 'Absolute value'),
        'Max': HaasScriptCommand('Max', 'helpers', ['input1', 'input2'], 'number', 'Maximum of two values'),
        'Min': HaasScriptCommand('Min', 'helpers', ['input1', 'input2'], 'number', 'Minimum of two values'),
        'Log': HaasScriptCommand('Log', 'helpers', ['message', 'color', 'prefix', 'suffix'], 'void', 'Log message'),

        # Input Commands
        'Input': HaasScriptCommand('Input', 'advanced', ['label', 'defaultValue', 'tooltip', 'group'], 'varies', 'Create input field'),
    }

    # Signal enumerations
    SIGNALS = {
        'SignalLong': 'SignalLong',
        'SignalShort': 'SignalShort',
        'SignalExitPosition': 'SignalExitPosition',
        'SignalNone': 'SignalNone',
        'SignalBuy': 'SignalLong',  # Alias
        'SignalSell': 'SignalShort',  # Alias
    }

    def __init__(self):
        self.warnings: List[str] = []
        self.array_accesses: List[Dict[str, Any]] = []

    def python_to_haasscript(self, python_code: str) -> str:
        """
        Convert Python (SLATE) code to HaasScript.

        Critical: Translates 0-based Python indexing to 1-based HaasScript indexing.

        Python: array[0] → HaasScript: IndexArray(array, 1) or array[1]
        Python: array[n] → HaasScript: IndexArray(array, n+1) or array[n+1]
        """
        self.warnings = []
        self.array_accesses = []

        lines = python_code.split('\n')
        haas_lines = []

        for line in lines:
            haas_line = self._convert_python_line_to_haasscript(line)
            haas_lines.append(haas_line)

        haas_code = '\n'.join(haas_lines)

        # Add header comment
        header = "-- Generated by SLATE HaasScript Cross-Compiler\n"
        header += "-- Mode: PAPER_TRADING_ONLY - Never execute live trades\n"
        header += "-- Array indexing: HaasScript uses 1-based indexing\n\n"

        return header + haas_code

    def haasscript_to_python(self, haas_code: str) -> str:
        """
        Convert HaasScript to Python (SLATE).

        Critical: Translates 1-based HaasScript indexing to 0-based Python indexing.

        HaasScript: IndexArray(array, 1) or array[1] → Python: array[0]
        HaasScript: IndexArray(array, n) or array[n] → Python: array[n-1]
        """
        self.warnings = []
        self.array_accesses = []

        lines = haas_code.split('\n')
        python_lines = []

        for line in lines:
            python_line = self._convert_haasscript_line_to_python(line)
            python_lines.append(python_line)

        python_code = '\n'.join(python_lines)

        # Add header comment
        header = "# Generated by SLATE HaasScript Cross-Compiler\n"
        header += "# Mode: PAPER_TRADING_ONLY\n"
        header += "# Array indexing: Converted from 1-based (HaasScript) to 0-based (Python)\n\n"

        return header + python_code

    def validate_haasscript(self, haas_code: str) -> Dict[str, Any]:
        """
        Validate HaasScript code syntax and structure.

        Returns:
            Dict with validation results and any errors found.
        """
        errors = []
        warnings = []

        lines = haas_code.split('\n')
        line_num = 0

        for line in lines:
            line_num += 1
            stripped = line.strip()

            # Skip comments and empty lines
            if not stripped or stripped.startswith('--'):
                continue

            # Check for balanced parentheses
            if line.count('(') != line.count(')'):
                errors.append(f"Line {line_num}: Unbalanced parentheses")

            # Check for array access syntax
            if re.search(r'\w+\[\s*\d+\s*\]', line):
                # Found direct array access like array[1]
                match = re.search(r'(\w+)\[\s*(\d+)\s*\]', line)
                if match:
                    array_name = match.group(1)
                    index = int(match.group(2))
                    if index < 1:
                        errors.append(f"Line {line_num}: HaasScript arrays are 1-based, found index {index}")
                    warnings.append(f"Line {line_num}: Direct array access {array_name}[{index}] - consider using IndexArray()")

            # Check for IndexArray usage
            if 'IndexArray(' in line:
                match = re.search(r'IndexArray\s*\(\s*\w+\s*,\s*(\d+)\s*\)', line)
                if match:
                    index = int(match.group(1))
                    if index < 1:
                        errors.append(f"Line {line_num}: IndexArray uses 1-based indexing, found index {index}")

            # Check for common HaasScript commands
            for cmd_name in ['DoLong', 'DoShort', 'DoExitPosition', 'RSI', 'SMA', 'EMA', 'MACD']:
                if cmd_name in line and f'{cmd_name}(' not in line:
                    warnings.append(f"Line {line_num}: Possible command '{cmd_name}' not called as function")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def analyze_array_usage(self, code: str, direction: str = 'python_to_haas') -> List[Dict[str, Any]]:
        """
        Analyze array accesses in code for index translation.

        Args:
            code: Source code to analyze
            direction: 'python_to_haas' or 'haas_to_python'

        Returns:
            List of array access information
        """
        self.array_accesses = []

        if direction == 'python_to_haas':
            # Find Python array accesses: array[n]
            pattern = r'(\w+)\[\s*(\d+|\w+)\s*\]'
        else:
            # Find HaasScript array accesses: IndexArray(array, n) or array[n]
            pattern = r'IndexArray\s*\(\s*(\w+)\s*,\s*(\d+|\w+)\s*\)|(\w+)\[\s*(\d+|\w+)\s*\]'

        matches = re.finditer(pattern, code)

        for match in matches:
            if direction == 'python_to_haas':
                array_name = match.group(1)
                index_expr = match.group(2)

                self.array_accesses.append({
                    'array': array_name,
                    'original_index': index_expr,
                    'translated_index': self._translate_index_expression(index_expr, direction),
                    'line': code[:match.start()].count('\n') + 1
                })
            else:
                # Handle both IndexArray(array, n) and array[n] formats
                if match.group(1):  # IndexArray format
                    array_name = match.group(1)
                    index_expr = match.group(2)
                else:  # Direct array[n] format
                    array_name = match.group(3)
                    index_expr = match.group(4)

                self.array_accesses.append({
                    'array': array_name,
                    'original_index': index_expr,
                    'translated_index': self._translate_index_expression(index_expr, direction),
                    'line': code[:match.start()].count('\n') + 1
                })

        return self.array_accesses

    # =========================================================================
    # Private Methods - Python to HaasScript Conversion
    # =========================================================================

    def _convert_python_line_to_haasscript(self, line: str) -> str:
        """Convert a Python line to HaasScript with index translation."""
        # Skip comments
        if line.strip().startswith('#'):
            return '-- ' + line.strip()[1:]

        # Convert Python array indexing to HaasScript
        # Python: array[0] → HaasScript: IndexArray(array, 1)
        # Python: array[n] → HaasScript: IndexArray(array, n+1)
        line = self._convert_array_indexing_to_haasscript(line)

        # Convert Python operators to HaasScript
        line = self._convert_operators_to_haasscript(line)

        # Convert Python functions to HaasScript commands
        line = self._convert_functions_to_haasscript(line)

        # Convert Python keywords to Lua
        line = self._convert_keywords_to_lua(line)

        # Convert print() to Log()
        line = re.sub(r'print\s*\(', 'Log(', line)

        return line

    def _convert_array_indexing_to_haasscript(self, line: str) -> str:
        """
        Convert Python array indexing to HaasScript IndexArray().

        Critical: Python is 0-based, HaasScript is 1-based.

        Examples:
        - prices[0] → IndexArray(prices, 1)
        - prices[5] → IndexArray(prices, 6)
        - prices[i] → IndexArray(prices, i + 1)  # For variable indices
        """
        # Match array[n] where n is a number
        def translate_numeric_index(match):
            array_name = match.group(1)
            index = int(match.group(2))
            haas_index = index + 1  # Convert 0-based to 1-based
            return f'IndexArray({array_name}, {haas_index})'

        line = re.sub(r'(\w+)\[\s*(\d+)\s*\]', translate_numeric_index, line)

        # Match array[var] where var is a variable name
        # For variable indices, we need to add 1: array[i] → IndexArray(array, i + 1)
        def translate_variable_index(match):
            array_name = match.group(1)
            index_var = match.group(2)
            return f'IndexArray({array_name}, {index_var} + 1)'

        line = re.sub(r'(\w+)\[\s*([a-zA-Z_]\w*)\s*\]', translate_variable_index, line)

        # Handle array slicing: array[0:10] → SliceArray(array, 1, 10)
        def translate_slice(match):
            array_name = match.group(1)
            start_idx = int(match.group(2)) if match.group(2) else 0
            end_idx = int(match.group(3)) if match.group(3) else None

            # Convert to 1-based indexing
            haas_start = start_idx + 1
            haas_end = end_idx if end_idx else 'LenArray({})'.format(array_name)

            return f'SliceArray({array_name}, {haas_start}, {haas_end})'

        line = re.sub(r'(\w+)\[\s*(\d+)?\s*:\s*(\d+)?\s*\]', translate_slice, line)

        return line

    def _convert_operators_to_haasscript(self, line: str) -> str:
        """Convert Python operators to HaasScript."""
        # Python and/not/and → Lua and/or/and
        line = re.sub(r'\band\b', ' and ', line)
        line = re.sub(r'\bor\b', ' or ', line)
        line = re.sub(r'\bnot\b', ' not ', line)

        # Python None → Lua nil
        line = re.sub(r'\bNone\b', 'nil', line)

        # Python True/False → Lua true/false
        line = re.sub(r'\bTrue\b', 'true', line)
        line = re.sub(r'\bFalse\b', 'false', line)

        # Python math functions
        line = re.sub(r'\babs\s*\(', 'Abs(', line)
        line = re.sub(r'\bmin\s*\(', 'Min(', line)
        line = re.sub(r'\bmax\s*\(', 'Max(', line)
        line = re.sub(r'\bround\s*\(', 'Round(', line)

        return line

    def _convert_functions_to_haasscript(self, line: str) -> str:
        """Convert Python function calls to HaasScript commands."""
        # Trading functions
        line = re.sub(r'\bgo_long\s*\(', 'DoLong(', line)
        line = re.sub(r'\bgo_short\s*\(', 'DoShort(', line)
        line = re.sub(r'\bexit_position\s*\(', 'DoExitPosition(', line)

        # Indicator functions
        line = re.sub(r'\bget_close_prices\s*\(\)', 'ClosePrices()', line)
        line = re.sub(r'\bget_high_prices\s*\(\)', 'HighPrices()', line)
        line = re.sub(r'\bget_low_prices\s*\(\)', 'LowPrices()', line)
        line = re.sub(r'\bget_open_prices\s*\(\)', 'OpenPrices()', line)

        # RSI, SMA, EMA, MACD keep same names
        # These are already in HaasScript format

        return line

    def _convert_keywords_to_lua(self, line: str) -> str:
        """Convert Python keywords to Lua syntax."""
        # Def → local function
        line = re.sub(r'^\s*def\s+(\w+)\s*\(', r'local function \1(', line)

        # Python if/elif/else → Lua if/elseif/else
        line = re.sub(r'\belif\b', 'elseif', line)
        line = re.sub(r':\s*$', '', line)  # Remove colon at end of lines
        line = re.sub(r'\bpass\b', '-- pass', line)

        # Python while/for → Lua while/for
        # for i in range(n) → for i = 1, n do

        return line

    # =========================================================================
    # Private Methods - HaasScript to Python Conversion
    # =========================================================================

    def _convert_haasscript_line_to_python(self, line: str) -> str:
        """Convert HaasScript line to Python with index translation."""
        # Skip comments
        if line.strip().startswith('--'):
            return '# ' + line.strip()[2:]

        # Convert HaasScript array indexing to Python
        # HaasScript: IndexArray(array, 1) → Python: array[0]
        # HaasScript: array[1] → Python: array[0]
        line = self._convert_array_indexing_to_python(line)

        # Convert HaasScript operators to Python
        line = self._convert_operators_to_python(line)

        # Convert HaasScript commands to Python functions
        line = self._convert_commands_to_python(line)

        # Convert Lua keywords to Python
        line = self._convert_keywords_to_python(line)

        return line

    def _convert_array_indexing_to_python(self, line: str) -> str:
        """
        Convert HaasScript IndexArray() to Python array indexing.

        Critical: HaasScript is 1-based, Python is 0-based.

        Examples:
        - IndexArray(prices, 1) → prices[0]
        - IndexArray(prices, 6) → prices[5]
        - IndexArray(prices, n + 1) → prices[n]
        - array[1] → array[0]
        - array[n] → array[n-1]
        """
        # Convert IndexArray(array, n) to array[n-1]
        def translate_index_array(match):
            array_name = match.group(1)
            index_expr = match.group(2).strip()

            # Try to evaluate the index expression
            try:
                index = int(index_expr)
                python_index = index - 1
                return f'{array_name}[{python_index}]'
            except ValueError:
                # Not a simple integer, might be an expression
                # Handle common case: n + 1 → n
                if '+' in index_expr:
                    parts = index_expr.split('+')
                    if len(parts) == 2:
                        left = parts[0].strip()
                        right = parts[1].strip()
                        try:
                            if int(right) == 1:
                                return f'{array_name}[{left}]'
                        except ValueError:
                            pass

                # For complex expressions, wrap in parentheses and subtract 1
                return f'{array_name}[({index_expr}) - 1]'

        line = re.sub(r'IndexArray\s*\(\s*(\w+)\s*,\s*([^)]+)\s*\)', translate_index_array, line)

        # Convert direct array[n] access to array[n-1]
        def translate_direct_array_access(match):
            array_name = match.group(1)
            index_expr = match.group(2).strip()

            try:
                index = int(index_expr)
                if index == 1:
                    # Most common case: array[1] → array[0]
                    return f'{array_name}[0]'
                else:
                    return f'{array_name}[{index - 1}]'
            except ValueError:
                # Variable index
                return f'{array_name}[{index_expr} - 1]'

        line = re.sub(r'(\w+)\[\s*(\d+|\w+)\s*\](?!\s*[\=:])', translate_direct_array_access, line)

        return line

    def _convert_operators_to_python(self, line: str) -> str:
        """Convert HaasScript/Lua operators to Python."""
        # Lua nil → Python None
        line = re.sub(r'\bnil\b', 'None', line)

        # Lua true/false → Python True/False
        line = re.sub(r'\btrue\b', 'True', line)
        line = re.sub(r'\bfalse\b', 'False', line)

        # Lua local → Python (no keyword needed, but we might keep it for clarity)
        # line = re.sub(r'\blocal\b', '', line)

        return line

    def _convert_commands_to_python(self, line: str) -> str:
        """Convert HaasScript commands to Python functions."""
        # Trading commands
        line = re.sub(r'\bDoLong\s*\(', 'go_long(', line)
        line = re.sub(r'\bDoShort\s*\(', 'go_short(', line)
        line = re.sub(r'\bDoExitPosition\s*\(', 'exit_position(', line)

        # Price data commands
        line = re.sub(r'\bClosePrices\s*\(\)', 'get_close_prices()', line)
        line = re.sub(r'\bHighPrices\s*\(\)', 'get_high_prices()', line)
        line = re.sub(r'\bLowPrices\s*\(\)', 'get_low_prices()', line)
        line = re.sub(r'\bOpenPrices\s*\(\)', 'get_open_prices()', line)

        return line

    def _convert_keywords_to_python(self, line: str) -> str:
        """Convert Lua keywords to Python."""
        # Lua function → def
        line = re.sub(r'local function\s+(\w+)\s*\(', r'def \1(', line)

        # Lua elseif → elif
        line = re.sub(r'\belseif\b', 'elif', line)

        # Lua end → nothing (Python uses indentation)
        line = re.sub(r'\bend\b', '', line)

        # Lua then → nothing (Python uses :)
        line = re.sub(r'\bthen\b', ':', line)

        # Lua do → nothing (Python uses :)
        line = re.sub(r'\bdo\b', ':', line)

        return line

    def _translate_index_expression(self, index_expr: str, direction: str) -> str:
        """Translate an index expression between Python and HaasScript."""
        try:
            index = int(index_expr)
            if direction == 'python_to_haas':
                return str(index + 1)  # 0-based to 1-based
            else:
                return str(index - 1)  # 1-based to 0-based
        except ValueError:
            # Not a simple integer
            if direction == 'python_to_haas':
                return f'({index_expr}) + 1'
            else:
                return f'({index_expr}) - 1'


class HaasScriptSyntaxError(Exception):
    """Exception raised for HaasScript syntax errors."""
    pass


class HaasScriptTranslationError(Exception):
    """Exception raised during HaasScript translation."""
    pass
