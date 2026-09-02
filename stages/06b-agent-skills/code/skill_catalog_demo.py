from pathlib import Path

from tiny_agent.skills import SkillCatalog


root = Path(__file__).resolve().parents[1] / "skills"
catalog = SkillCatalog(root)

print("--- startup metadata only ---")
print(catalog.metadata_prompt())

print("\n--- activate on demand ---")
active = catalog.activate("research-review")
print(active.instructions)
print("references:", [path.name for path in active.references])
print("declared allowed-tools (metadata only):", active.descriptor.allowed_tools)
