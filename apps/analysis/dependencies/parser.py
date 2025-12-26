"""Parse dependency files (pom.xml, requirements.txt, composer.json)."""
import logging
import xml.etree.ElementTree as ET
import json
import re
from typing import List, Optional
from pathlib import Path
from apps.analysis.dependencies.models import Dependency

logger = logging.getLogger(__name__)


class DependencyParser:
    """Parser for dependency files."""
    
    def parse_file(self, content: str, path: str) -> List[Dependency]:
        """
        Parse a dependency file.
        
        Args:
            content: File content
            path: File path
            
        Returns:
            List of dependencies
        """
        file_path = Path(path)
        ext = file_path.suffix.lower()
        name = file_path.name.lower()
        
        if name == 'pom.xml' or ext == '.xml':
            return self._parse_maven(content, path)
        elif name == 'requirements.txt' or name.endswith('requirements.txt'):
            return self._parse_pip(content, path)
        elif name == 'composer.json':
            return self._parse_composer(content, path)
        else:
            logger.warning(f"Unknown dependency file type: {path}")
            return []
    
    def _parse_maven(self, content: str, path: str) -> List[Dependency]:
        """Parse Maven pom.xml."""
        dependencies = []
        
        try:
            root = ET.fromstring(content)
            
            # Handle namespaces
            ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
            
            # Find all dependency elements
            deps = root.findall('.//maven:dependency', ns)
            if not deps:
                # Try without namespace
                deps = root.findall('.//dependency')
            
            for dep in deps:
                group_id_elem = dep.find('groupId', ns) or dep.find('groupId')
                artifact_id_elem = dep.find('artifactId', ns) or dep.find('artifactId')
                version_elem = dep.find('version', ns) or dep.find('version')
                
                if group_id_elem is not None and artifact_id_elem is not None:
                    group_id = group_id_elem.text or ''
                    artifact_id = artifact_id_elem.text or ''
                    version = version_elem.text if version_elem is not None else 'unknown'
                    
                    # Full name: groupId:artifactId
                    name = f"{group_id}:{artifact_id}"
                    
                    dependencies.append(Dependency(
                        name=name,
                        version=version,
                        package_manager='maven',
                        file_path=path,
                    ))
        
        except ET.ParseError as e:
            logger.warning(f"Failed to parse Maven pom.xml {path}: {e}")
        except Exception as e:
            logger.exception(f"Error parsing Maven file {path}: {e}")
        
        return dependencies
    
    def _parse_pip(self, content: str, path: str) -> List[Dependency]:
        """Parse pip requirements.txt."""
        dependencies = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse requirement line
            # Format: package==version or package>=version or package~=version etc.
            # Also handle: -r other_file.txt, -e git+..., etc.
            
            # Skip special directives
            if line.startswith('-r') or line.startswith('--') or line.startswith('-e'):
                continue
            
            # Extract package name and version
            # Match: package==1.2.3, package>=1.2.3, package~=1.2.3, package
            match = re.match(r'^([a-zA-Z0-9_\-\.]+)(?:([=~<>!]+)(.+))?', line)
            if match:
                package_name = match.group(1)
                version = match.group(3) if match.group(3) else 'unknown'
                
                dependencies.append(Dependency(
                    name=package_name,
                    version=version,
                    package_manager='pip',
                    file_path=path,
                    line_number=line_num,
                ))
        
        return dependencies
    
    def _parse_composer(self, content: str, path: str) -> List[Dependency]:
        """Parse Composer composer.json."""
        dependencies = []
        
        try:
            data = json.loads(content)
            
            # Parse require section
            require = data.get('require', {})
            require_dev = data.get('require-dev', {})
            
            for package_name, version_constraint in {**require, **require_dev}.items():
                # Skip PHP version requirement
                if package_name == 'php' or package_name.startswith('ext-'):
                    continue
                
                dependencies.append(Dependency(
                    name=package_name,
                    version=version_constraint,
                    package_manager='composer',
                    file_path=path,
                ))
        
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Composer composer.json {path}: {e}")
        except Exception as e:
            logger.exception(f"Error parsing Composer file {path}: {e}")
        
        return dependencies
