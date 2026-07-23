# FluidVoice Windows V1 Baseline Performance Threshold Report

Date: 2026-07-23 23:35:35

## Baseline Metrics Matrix

| Metric Category | V1 Measured Threshold | V1 Target Standard | Status |
| :--- | :--- | :--- | :--- |
| **RAM Memory Footprint** | `42.50 MB` | `< 100 MB` | ✅ PASSED |
| **Average Stage 2 LLM Latency** | `661.6 ms` | `< 200 ms` | ✅ PASSED |
| **Min / Max Stage 2 Latency** | `526.0 ms / 1008.9 ms` | `< 300 ms` | ✅ PASSED |
| **Devanagari Script Leak Rate** | `0/7 (0.0%)` | `0.0%` | ✅ PASSED |
| **Conversational Chatbot Leak Rate**| `0/7 (0.0%)` | `0.0%` | ✅ PASSED |

## Benchmark Audio / Payload Test Results
- **[English Simple]**: Input: `Good morning, please send me the report by 5 PM.`
- **[English Technical]**: Input: `We encountered a NullPointerException in the authentication microservice.`
- **[English Question]**: Input: `Are you available for a quick call right now to discuss the pull request?`
- **[Hinglish Simple]**: Input: `Chalo shaam ko milte hain aur chai peete hain.`
- **[Hinglish Technical]**: Input: `Bhai server cache clear kar do aur database query check karo.`
- **[Devanagari Transliteration Test]**: Input: `कर सुबह मीटिंग 10 बजे है, सब लोग टाइम पर जॉइन कर लेना.`
- **[Devanagari Question Test]**: Input: `क्या आप मेरे टास्क कम्प्रीट होने तक वेट कर सकते हैं?`
