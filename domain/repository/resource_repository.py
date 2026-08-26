"""文献集合、词典与导出资源的仓储契约。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IResourceRepository(ABC):
    @abstractmethod
    def create_collection(self, workspace_id: str, name: str, description: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]: ...

    @abstractmethod
    def list_collections(self, workspace_id: str, limit: int = 100) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def get_collection(self, collection_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def create_dictionary(self, workspace_id: str, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    @abstractmethod
    def list_dictionaries(self, workspace_id: str, limit: int = 100) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def get_dictionary(self, dictionary_id: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def delete_dictionary(self, dictionary_id: str) -> bool: ...

    @abstractmethod
    def create_export(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    @abstractmethod
    def get_export(self, export_id: str) -> Optional[Dict[str, Any]]: ...
