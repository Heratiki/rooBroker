import pytest
import json
from unittest.mock import mock_open
from rooBroker.core.state import save_model_state, load_model_state, load_models_as_list
from pathlib import Path

def test_save_model_state_success(mocker):
    # Arrange
    test_data = [
        {'id': 'model-1', 'score': 0.8},
        {'id': 'model-2', 'score': 0.9}
    ]
    test_file_path = "test_state.json"

    # Mock the built-in open function
    mocked_open = mocker.patch('builtins.open', mock_open())

    # Mock json.dump
    mock_json_dump = mocker.patch('json.dump')

    # Act
    save_model_state(data=test_data, file_path=test_file_path, console=None)

    # Assert
    mocked_open.assert_called_once_with(test_file_path, "w", encoding="utf-8")

    # Check json.dump call
    dump_args, dump_kwargs = mock_json_dump.call_args
    assert dump_args[0] == {
        'model-1': {'id': 'model-1', 'score': 0.8},
        'model-2': {'id': 'model-2', 'score': 0.9}
    }
    assert dump_kwargs["indent"] == 2
    assert dump_kwargs["ensure_ascii"] is False

def test_load_model_state_success(mocker):
    # Arrange
    test_file_path = "test_state.json"
    expected_data = {
        'model-1': {'id': 'model-1', 'score': 0.8},
        'model-2': {'id': 'model-2', 'score': 0.9}
    }

    # Mock Path.exists to return True
    mock_path = mocker.patch('pathlib.Path')
    mock_path.return_value.exists.return_value = True

    # Mock the built-in open function and json.load
    mock_file = mocker.mock_open(read_data=json.dumps(expected_data))
    mocker.patch('builtins.open', mock_file)
    mock_json_load = mocker.patch('json.load', return_value=expected_data)

    # Act
    result = load_model_state(file_path=test_file_path, console=None)

    # Assert
    assert result == expected_data
    mock_path.return_value.exists.assert_called_once()
    mock_file.assert_called_once_with(test_file_path, 'r', encoding='utf-8')
    mock_json_load.assert_called_once()

def test_load_model_state_file_not_found(mocker):
    # Arrange
    test_file_path = "non_existent_state.json"

    # Mock Path.exists to return False
    mock_path_exists = mocker.patch('pathlib.Path.exists', return_value=False)

    # Mock the built-in open function
    mock_open = mocker.patch('builtins.open', mocker.mock_open())

    # Act
    result = load_model_state(file_path=test_file_path, console=None)

    # Assert
    assert result == {}
    mock_path_exists.assert_called_once()
    mock_open.assert_not_called()

def test_load_model_state_json_error(mocker):
    # Arrange
    test_file_path = "invalid_state.json"

    # Mock Path.exists to return True
    mock_path_exists = mocker.patch('pathlib.Path.exists', return_value=True)

    # Mock the built-in open function
    mocker.patch('builtins.open', mocker.mock_open())

    # Mock json.load to raise a JSONDecodeError
    mock_json_load = mocker.patch('json.load', side_effect=json.JSONDecodeError('Expecting value', 'doc', 0))

    # Act
    result = load_model_state(file_path=test_file_path, console=None)

    # Assert
    assert result == {}
    mock_path_exists.assert_called_once()
    mocker.patch('builtins.open').assert_called_once_with(test_file_path, 'r', encoding='utf-8')
    mock_json_load.assert_called_once()

def test_load_models_as_list_success(mocker):
    # Arrange
    test_file_path = "dummy_path.json"
    mock_state_dict = {
        'model-a': {'id': 'model-a'},
        'model-b': {'id': 'model-b'}
    }
    expected_list = [
        {'id': 'model-a'},
        {'id': 'model-b'}
    ]
    mock_load = mocker.patch('rooBroker.core.state.load_model_state', return_value=mock_state_dict)

    # Act
    result = load_models_as_list(file_path=test_file_path, console=None)

    # Assert
    assert result == expected_list
    mock_load.assert_called_once_with(test_file_path, None)

def test_load_models_as_list_empty(mocker):
    # Arrange
    test_file_path = "dummy_path.json"
    mock_load = mocker.patch('rooBroker.core.state.load_model_state', return_value={})

    # Act
    result = load_models_as_list(file_path=test_file_path, console=None)

    # Assert
    assert result == []
    mock_load.assert_called_once_with(test_file_path, None)
