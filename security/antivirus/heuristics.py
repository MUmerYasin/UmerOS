"""Heuristic analysis engine for zero-day and unknown threats."""

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class HeuristicVerdict(Enum):
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


@dataclass
class HeuristicResult:
    verdict: HeuristicVerdict
    score: float  # 0.0 = clean, 1.0 = definitely malicious
    reasons: List[str]
    suggestions: List[str]


class HeuristicAnalyzer:
    """Static heuristic analysis for detecting unknown malware patterns."""

    DANGEROUS_PATTERNS = [
        (r"eval\s*\(\s*base64_decode", "Obfuscated code via eval+base64"),
        (r"exec\s*\(\s*chr\(", "Obfuscated code via exec+chr"),
        (r"System\.Reflection\.Assembly.*Load", ".NET dynamic assembly loading"),
        (r"powershell.*-enc\s+[A-Za-z0-9+/=]{20,}", "Encoded PowerShell command"),
        (r"cmd\.exe.*/c.*del.*(/s|/q)", "Mass file deletion attempt"),
        (r"HKEY_LOCAL_MACHINE.*RunOnce", "Persistence via registry RunOnce"),
        (r"\\\\\\.\\pipe\\", "Named pipe communication (C2 channel)"),
        (r"CreateRemoteThread", "Process injection via remote thread"),
        (r"VirtualAllocEx.*MEM_COMMIT", "Memory allocation in remote process"),
        (r"WriteProcessMemory", "Writing to remote process memory"),
        (r"mimikatz|sekurlsa::logonpasswords", "Credential dumping tool detected"),
        (r"Invoke-Mimikatz|Invoke-TokenManipulate", "PowerShell post-exploitation"),
        (r"reverse_tcp.*\d+\.\d+\.\d+\.\d+", "Reverse shell TCP connection"),
        (r"base64_decode\s*\(\s*\$_(GET|POST|REQUEST)", "Web shell obfuscation"),
        (r"shell_exec\s*\(\s*\$_(GET|POST)", "PHP web shell execution"),
        (r"<%.*eval\s+request", "ASP web shell detected"),
        (r"wget\s+.*\|\s*sh", "Remote script execution via pipe"),
        (r"curl\s+.*\|\s*(ba)?sh", "Remote script execution via pipe"),
    ]

    HIGH_ENTROPY_THRESHOLD = 7.5  # Random/encrypted content
    PE_SUSPICIOUS_SECTIONS = [".upx", ".aspack", ".vmp", ".themida"]
    RANSOM_KEYWORDS = [
        "decrypt", "recover", "bitcoin", "wallet", "ransom",
        "encrypted", "pay", "deadline", "btc", "monero",
    ]

    def analyze(self, file_path: str) -> HeuristicResult:
        score = 0.0
        reasons = []
        suggestions = []

        try:
            with open(file_path, "rb") as f:
                content = f.read()
        except (PermissionError, OSError) as e:
            return HeuristicResult(
                verdict=HeuristicVerdict.SUSPICIOUS,
                score=0.3,
                reasons=[f"Cannot read file: {e}"],
                suggestions=["Check file permissions"],
            )

        text_content = content.decode("utf-8", errors="ignore")

        # Pattern matching
        for pattern, desc in self.DANGEROUS_PATTERNS:
            if re.search(pattern, text_content, re.IGNORECASE):
                score += 0.3
                reasons.append(f"Suspicious pattern: {desc}")

        # Entropy analysis
        entropy = self._calculate_entropy(content)
        if entropy > self.HIGH_ENTROPY_THRESHOLD:
            score += 0.2
            reasons.append(f"High entropy ({entropy:.2f}) - possible packed/encrypted")

        # PE header analysis (Windows executables)
        if content[:2] == b"MZ":
            score += 0.1
            reasons.append("Windows executable (PE) detected")
            for section in self.PE_SUSPICIOUS_SECTIONS:
                if section.encode() in content:
                    score += 0.2
                    reasons.append(f"Packer section detected: {section}")

        # Ransom note detection
        text_lower = text_content.lower()
        ransom_hits = sum(1 for kw in self.RANSOM_KEYWORDS if kw in text_lower)
        if ransom_hits >= 3:
            score += 0.4
            reasons.append(f"Ransomware indicators found ({ransom_hits} keywords)")

        # Script file analysis
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".ps1", ".bat", ".cmd"):
            score += 0.15
            reasons.append(f"Script file type: {ext}")

        # Determine verdict
        score = min(score, 1.0)
        if score >= 0.7:
            verdict = HeuristicVerdict.MALICIOUS
            suggestions.append("Quarantine this file immediately")
        elif score >= 0.3:
            verdict = HeuristicVerdict.SUSPICIOUS
            suggestions.append("Run full system scan")
            suggestions.append("Submit for manual analysis")
        else:
            verdict = HeuristicVerdict.CLEAN

        return HeuristicResult(
            verdict=verdict,
            score=round(score, 3),
            reasons=reasons or ["No suspicious patterns found"],
            suggestions=suggestions,
        )

    def _calculate_entropy(self, data: bytes) -> float:
        import math
        if not data:
            return 0.0
        freq = [0] * 256
        for byte in data:
            freq[byte] += 1
        length = len(data)
        entropy = 0.0
        for count in freq:
            if count > 0:
                p = count / length
                entropy -= p * math.log2(p)
        return entropy

    def analyze_text(self, text: str) -> HeuristicResult:
        score = 0.0
        reasons = []
        for pattern, desc in self.DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                score += 0.3
                reasons.append(f"Suspicious pattern: {desc}")
        score = min(score, 1.0)
        verdict = (
            HeuristicVerdict.MALICIOUS if score >= 0.7
            else HeuristicVerdict.SUSPICIOUS if score >= 0.3
            else HeuristicVerdict.CLEAN
        )
        return HeuristicResult(verdict=verdict, score=round(score, 3), reasons=reasons or ["Clean"], suggestions=[])
