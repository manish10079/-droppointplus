# DropPoint+ Development Skills

## 1. Architecture Skill

### Purpose

Design scalable, maintainable, and extensible application architectures.

Focus on: - Separation of concerns - Low coupling - High cohesion -
Testability - Maintainability - Extensibility

Avoid: - Giant classes - Business logic inside UI - Hidden
dependencies - Global state abuse

## Recommended Layers

    Application
    |
    ├── Presentation Layer
    │   ├── UI
    │   ├── Views
    │   └── View Models
    |
    ├── Application Layer
    │   ├── Use Cases
    │   ├── Controllers
    │   └── Coordinators
    |
    ├── Domain Layer
    │   ├── Models
    │   ├── Entities
    │   └── Business Rules
    |
    └── Infrastructure Layer
        ├── File System
        ├── Database
        ├── Network
        └── External Services

Dependencies should flow inward.

    UI
     ↓
    Application
     ↓
    Domain
     ↓
    Infrastructure

------------------------------------------------------------------------

# 2. Python Development Skill

## Purpose

Write clean, production-quality Python applications.

Use: - Python 3.12+ - pathlib - dataclasses - type hints - modern
standard library features

Follow: - PEP 8 - Small functions - Clear naming - Explicit code

## Type Safety

Always use type hints.

Example:

``` python
def copy_file(source: Path, destination: Path) -> bool:
    pass
```

Prefer dataclasses for models.

Example:

``` python
@dataclass
class FileItem:
    path: Path
    size: int
```

Never silently ignore exceptions.

Use logging instead of print.

For heavy operations use: - threading - multiprocessing - queues

------------------------------------------------------------------------

# 3. PySide6 Qt Skill

## Purpose

Build professional cross-platform desktop applications using PySide6 and
Qt6.

Use: - PySide6 - Qt6 - MVVM/MVC style architecture

Never put business logic inside widgets.

Correct flow:

    UI
     |
    ViewModel
     |
    Service
     |
    Infrastructure

Use signals and slots for communication.

Long operations must never block the UI thread.

Use: - QThread - QRunnable - QThreadPool

Create reusable widgets:

    widgets/

    ├── FileCard.py
    ├── DropZone.py
    ├── ProgressWidget.py
    └── SearchBox.py

Support: - High DPI - Window resizing - Multiple platforms - Adaptive
layouts

Avoid fixed positioning.

------------------------------------------------------------------------

# 4. Decoupled Application Development Skill

## Purpose

Create applications where components can evolve independently.

Golden rule:

UI decides WHAT should happen.

Services decide HOW it happens.

Correct flow:

    User Action

    ↓

    UI Layer

    ↓

    Controller

    ↓

    Service

    ↓

    Repository / Infrastructure

    ↓

    Event Result

    ↓

    UI Update

## Dependency Injection

Prefer:

``` python
class Controller:
    def __init__(self, service):
        self.service = service
```

Avoid:

``` python
class Controller:
    service = FileService()
```

## Event Driven Communication

Use events such as:

-   FileCopiedEvent
-   OperationCompletedEvent
-   ErrorEvent

## Background Operations

Separate:

    Operation Manager

          |

    Worker Thread

          |

    File System

## Replaceability Test

A good architecture should allow:

-   Replace database
-   Replace UI
-   Replace storage engine
-   Add plugins
-   Add features
-   Write tests

without rewriting the entire application.
