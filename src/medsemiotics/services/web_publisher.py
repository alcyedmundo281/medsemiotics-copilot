"""Service for publishing interactive modules to the PowerSemiotics web portal.

Manages:
1. Verification and copying of module HTML into the section directory.
2. Canonical link injection/updating.
3. Card creation and insertion into the section hub (e.g. gastroenterologia.html).
4. Sitemap regeneration.
5. Optional Git commit and push to main in the medsemiotics repository.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import date
from pathlib import Path

from medsemiotics.domain.web_publication import (
    CourseWebSection,
    WebModuleSpec,
    WebPublishPlan,
    WebPublishResult,
)

logger = logging.getLogger(__name__)

# Default locations to search for the medsemiotics web repository
DEFAULT_SEARCH_PATHS: list[Path] = [
    Path("c:/Users/aetorres/Documents/medsemiotics"),
    Path(__file__).resolve().parent.parent.parent.parent / "medsemiotics",
]


class WebPublisherError(Exception):
    """Base exception for web publisher service failures."""


class WebPublisher:
    """Orchestrates web publishing of educational modules to PowerSemiotics."""

    def __init__(self, web_repo_dir: Path | None = None) -> None:
        """Initialize the publisher, resolving the target web repository root."""
        self.web_repo_dir = self._resolve_web_repo_dir(web_repo_dir)

    @staticmethod
    def _resolve_web_repo_dir(explicit_path: Path | None = None) -> Path:
        """Resolve the medsemiotics repository directory."""
        if explicit_path is not None:
            resolved = explicit_path.resolve()
            if not (resolved / ".git").is_dir() and not (resolved / "index.html").is_file():
                msg = f"Provided path is not a valid medsemiotics repository: {resolved}"
                raise WebPublisherError(msg)
            return resolved

        # Check environment variable
        env_val = os.getenv("MEDSEMIOTICS_WEB_REPO_PATH")
        if env_val:
            env_path = Path(env_val).resolve()
            if env_path.is_dir():
                return env_path

        for candidate in DEFAULT_SEARCH_PATHS:
            if candidate.is_dir() and (candidate / ".git").is_dir():
                return candidate.resolve()

        msg = (
            "Could not locate the medsemiotics web repository. Set MEDSEMIOTICS_WEB_REPO_PATH "
            "or pass the directory explicitly."
        )
        raise WebPublisherError(msg)

    def plan_publish(self, spec: WebModuleSpec) -> WebPublishPlan:
        """Build a deterministic, reviewable publish plan without modifying any files."""
        if not spec.source_html_path.is_file():
            msg = f"Source HTML file does not exist: {spec.source_html_path}"
            raise WebPublisherError(msg)

        section = CourseWebSection.from_course(spec.course)
        target_dir = self.web_repo_dir / section.section_slug
        target_module_path = target_dir / f"{spec.slug}.html"
        target_hub_path = self.web_repo_dir / section.hub_filename

        if not target_hub_path.is_file():
            msg = f"Section hub file does not exist in web repository: {target_hub_path}"
            raise WebPublisherError(msg)

        relative_href = spec.get_relative_href(section.section_slug)
        canonical_url = spec.get_canonical_url(section.section_slug)

        card_html = self.format_card_html(
            title=spec.title,
            description=spec.description,
            relative_href=relative_href,
            icon=spec.icon,
        )

        hub_content = target_hub_path.read_text(encoding="utf-8")
        card_already_exists = relative_href in hub_content or f"{spec.slug}.html" in hub_content

        return WebPublishPlan(
            spec=spec,
            section=section,
            target_module_path=target_module_path,
            target_hub_path=target_hub_path,
            card_html=card_html,
            card_already_exists=card_already_exists,
            canonical_url=canonical_url,
            relative_href=relative_href,
        )

    @staticmethod
    def format_card_html(
        title: str,
        description: str,
        relative_href: str,
        icon: str,
    ) -> str:
        """Render the standard Tailwind card HTML used in course hubs."""
        clean_title = title.strip()
        lower_title = clean_title.lower()
        if not (lower_title.startswith("módulo:") or lower_title.startswith("modulo:")):
            heading = f"Módulo: {clean_title}"
        else:
            heading = clean_title

        return (
            f"        <!-- {heading} -->\n"
            f"        <a\n"
            f'          href="{relative_href}"\n'
            f'          class="block w-full bg-white p-8 rounded-xl shadow-lg hover:shadow-2xl '
            f'transition-all duration-300 border border-gray-200 group card-hover-effect"\n'
            f"        >\n"
            f'          <div class="flex items-center mb-4">\n'
            f'            <i class="fas fa-{icon} text-4xl gradient-text"></i>\n'
            f"          </div>\n"
            f'          <h2 class="text-2xl font-bold text-gray-800">\n'
            f"            {heading}\n"
            f"          </h2>\n"
            f'          <p class="text-gray-600 text-md mt-2">\n'
            f"            {description.strip()}\n"
            f"          </p>\n"
            f"        </a>"
        )

    @staticmethod
    def ensure_canonical_link(html_content: str, canonical_url: str) -> str:
        """Ensure the HTML document has the correct canonical link in <head>."""
        canonical_tag = f'    <link rel="canonical" href="{canonical_url}" />\n'

        canonical_pattern = re.compile(
            r'<link\s+[^>]*rel=["\']canonical["\'][^>]*>',
            re.IGNORECASE,
        )

        if canonical_pattern.search(html_content):
            return canonical_pattern.sub(
                f'<link rel="canonical" href="{canonical_url}" />',
                html_content,
            )

        head_open_match = re.search(r"<head\b[^>]*>", html_content, re.IGNORECASE)
        if head_open_match:
            insert_pos = head_open_match.end()
            return f"{html_content[:insert_pos]}\n{canonical_tag}{html_content[insert_pos:]}"

        return html_content

    @staticmethod
    def inject_card_into_hub(hub_html: str, card_html: str, relative_href: str) -> str:
        """Inject or update a module card in the hub's card grid."""
        # If already present, don't duplicate
        if relative_href in hub_html:
            return hub_html

        # Match the end of the cards grid before closing </main> or </div>\n    </main>
        # Looking for the closing </div> of the grid
        grid_closing_pattern = re.compile(
            r"(\s*</div>\s*</main>)",
            re.IGNORECASE,
        )

        match = grid_closing_pattern.search(hub_html)
        if match:
            insert_point = match.start()
            new_hub = f"{hub_html[:insert_point]}\n\n{card_html}\n{hub_html[insert_point:]}"
            return new_hub

        msg = "Could not locate card grid closing tags in the hub HTML."
        raise WebPublisherError(msg)

    def update_sitemap(self) -> bool:
        """Regenerate or update the repository sitemap.xml."""
        sitemap_script = self.web_repo_dir / "tools" / "sitemap.mjs"
        if sitemap_script.is_file():
            try:
                proc = subprocess.run(
                    ["node", str(sitemap_script)],
                    cwd=str(self.web_repo_dir),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0:
                    logger.info(
                        "Regenerated sitemap.xml via tools/sitemap.mjs: %s",
                        proc.stdout.strip(),
                    )
                    return True
                logger.warning(
                    "node tools/sitemap.mjs exited with code %d: %s",
                    proc.returncode,
                    proc.stderr,
                )
            except Exception as err:
                logger.warning("Could not run node tools/sitemap.mjs: %s", err)

        # Fallback XML update
        return self._fallback_sitemap_update()

    def _fallback_sitemap_update(self) -> bool:
        """Directly insert URLs into sitemap.xml if script execution is unavailable."""
        sitemap_path = self.web_repo_dir / "sitemap.xml"
        if not sitemap_path.is_file():
            return False

        content = sitemap_path.read_text(encoding="utf-8")
        today = date.today().isoformat()

        # Find all HTML files in web_repo
        added_count = 0
        for html_file in self.web_repo_dir.glob("*/**/*.html"):
            rel_str = html_file.relative_to(self.web_repo_dir).as_posix()
            if rel_str.endswith("/index.html"):
                continue
            url = f"https://powersemiotics.com/medsemiotics/{rel_str}"
            if url not in content:
                entry = (
                    f"  <url>\n"
                    f"    <loc>{url}</loc>\n"
                    f"    <lastmod>{today}</lastmod>\n"
                    f"    <priority>0.6</priority>\n"
                    f"  </url>\n"
                )
                close_tag = "</urlset>"
                if close_tag in content:
                    content = content.replace(close_tag, f"{entry}{close_tag}")
                    added_count += 1

        if added_count > 0:
            sitemap_path.write_text(content, encoding="utf-8")
            return True
        return True

    def publish_module(
        self,
        plan: WebPublishPlan,
        auto_git: bool = False,
        commit_message: str | None = None,
    ) -> WebPublishResult:
        """Execute the web publication plan."""
        # 1. Ensure target directory exists
        plan.target_module_path.parent.mkdir(parents=True, exist_ok=True)

        # 2. Read, inject canonical, and write target module
        source_html = plan.spec.source_html_path.read_text(encoding="utf-8")
        prepared_html = self.ensure_canonical_link(source_html, plan.canonical_url)
        plan.target_module_path.write_text(prepared_html, encoding="utf-8")
        module_copied = plan.target_module_path.is_file()

        # 3. Inject card into hub
        hub_html = plan.target_hub_path.read_text(encoding="utf-8")
        hub_updated = False
        if not plan.card_already_exists:
            new_hub_html = self.inject_card_into_hub(
                hub_html=hub_html,
                card_html=plan.card_html,
                relative_href=plan.relative_href,
            )
            plan.target_hub_path.write_text(new_hub_html, encoding="utf-8")
            hub_updated = True
        else:
            hub_updated = True  # Already present and valid

        # 4. Update sitemap
        sitemap_updated = self.update_sitemap()

        # 5. Git commit and push if requested
        git_committed = False
        git_pushed = False

        if auto_git:
            files_to_add = [
                str(plan.target_module_path.relative_to(self.web_repo_dir)),
                str(plan.target_hub_path.relative_to(self.web_repo_dir)),
            ]
            sitemap_path = self.web_repo_dir / "sitemap.xml"
            if sitemap_path.is_file():
                files_to_add.append("sitemap.xml")

            msg = (
                commit_message
                or f"feat({plan.section.section_slug}): publica módulo {plan.spec.slug}"
            )

            git_committed, git_pushed = self._git_commit_and_push(files_to_add, msg)

        summary = (
            f"Módulo publicado exitosamente:\n"
            f"- Archivo destino: {plan.target_module_path}\n"
            f"- Hub actualizado: {plan.target_hub_path}\n"
            f"- URL Canónica: {plan.canonical_url}\n"
            f"- Tarjeta en hub: {'Agregada' if not plan.card_already_exists else 'Ya existía'}\n"
            f"- Git commit: {'Sí' if git_committed else 'No'}\n"
            f"- Git push: {'Sí' if git_pushed else 'No'}"
        )

        return WebPublishResult(
            module_copied=module_copied,
            hub_updated=hub_updated,
            sitemap_updated=sitemap_updated,
            git_committed=git_committed,
            git_pushed=git_pushed,
            published_url=plan.canonical_url,
            summary=summary,
        )

    def _git_commit_and_push(self, relative_files: list[str], message: str) -> tuple[bool, bool]:
        """Commit and push changes in the web repository."""
        try:
            # Stage files
            cmd_add = ["git", "add", *relative_files]
            subprocess.run(cmd_add, cwd=str(self.web_repo_dir), check=True, capture_output=True)

            # Check if there are staged changes
            diff_proc = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(self.web_repo_dir),
                check=False,
            )
            if diff_proc.returncode == 0:
                logger.info("No changes to commit in %s", self.web_repo_dir)
                return False, False

            # Commit
            cmd_commit = ["git", "commit", "-m", message]
            subprocess.run(cmd_commit, cwd=str(self.web_repo_dir), check=True, capture_output=True)
            committed = True

            # Push
            cmd_push = ["git", "push", "origin", "main"]
            push_proc = subprocess.run(
                cmd_push,
                cwd=str(self.web_repo_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            pushed = push_proc.returncode == 0

            return committed, pushed
        except Exception as err:
            logger.error("Git operation failed in %s: %s", self.web_repo_dir, err)
            return False, False
