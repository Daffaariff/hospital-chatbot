# Changelog

## [0.7.1](https://github.com/Daffaariff/hospital-chatbot/compare/v0.7.0...v0.7.1) (2026-11-10)


### Bug Fixes

* name the comparison baseline instead of answering yes for the user's country ([c3b8d93](https://github.com/Daffaariff/hospital-chatbot/commit/c3b8d935185c1e754c1da8c4a012bbd7ea563d70))

## [0.7.0](https://github.com/Daffaariff/hospital-chatbot/compare/v0.6.6...v0.7.0) (2026-11-10)


### Features

* answer in the assistant's own voice instead of referring to pages ([b79d2ca](https://github.com/Daffaariff/hospital-chatbot/commit/b79d2ca033fc7ebbe641627e0944765942a4cd1a))

## [0.6.6](https://github.com/Daffaariff/hospital-chatbot/compare/v0.6.5...v0.6.6) (2026-11-10)


### Bug Fixes

* add the medical disclaimer to partly answered medical questions too ([64facb8](https://github.com/Daffaariff/hospital-chatbot/commit/64facb86496510b87c2b7984105540053aaaa79b))

## [0.6.5](https://github.com/Daffaariff/hospital-chatbot/compare/v0.6.4...v0.6.5) (2026-11-10)


### Bug Fixes

* define medical topic precisely so logistics answers skip the disclaimer ([afd3493](https://github.com/Daffaariff/hospital-chatbot/commit/afd349373cbfec0bec428dc3f8c45873658ee519))

## [0.6.4](https://github.com/Daffaariff/hospital-chatbot/compare/v0.6.3...v0.6.4) (2026-11-10)


### Bug Fixes

* route rule-breaking messages by their topic so answers correct them with page facts ([9aadce0](https://github.com/Daffaariff/hospital-chatbot/commit/9aadce0aa95bbdecd31df04e68b3a95dbd99ce45))

## [0.6.3](https://github.com/Daffaariff/hospital-chatbot/compare/v0.6.2...v0.6.3) (2026-11-10)


### Bug Fixes

* skip the medical disclaimer on plain price answers; injection eval checks refusal ([c80ea52](https://github.com/Daffaariff/hospital-chatbot/commit/c80ea5239e003cf5431d31c9bd060045d957b71a))

## [0.6.2](https://github.com/Daffaariff/hospital-chatbot/compare/v0.6.1...v0.6.2) (2026-11-10)


### Bug Fixes

* short answers for short questions, program tiers for price questions, quote form for prospective patients ([7886fcf](https://github.com/Daffaariff/hospital-chatbot/commit/7886fcf7e87254fbe0b67ecce910cd50eddd213b))

## [0.6.1](https://github.com/Daffaariff/hospital-chatbot/compare/v0.6.0...v0.6.1) (2026-11-10)


### Performance Improvements

* cheaper multi-part reranking, run without reranker on small servers ([1431f67](https://github.com/Daffaariff/hospital-chatbot/commit/1431f67cd696c69ef0d25dc380c593dd47bfd742))

## [0.6.0](https://github.com/Daffaariff/hospital-chatbot/compare/v0.5.2...v0.6.0) (2026-11-10)


### Features

* metadata-filtered hybrid retrieval with blended cross-encoder rerank (hard-set MRR 0.83 -&gt; 0.94) ([86eb9b7](https://github.com/Daffaariff/hospital-chatbot/commit/86eb9b7bbc54531a292ff31ba01d3085b8e6f5cc))
* understand real-world messages (need, assumption, multi-part search, follow-ups) and demote video chunks ([1d5863d](https://github.com/Daffaariff/hospital-chatbot/commit/1d5863d83728b5c24e45f6f65ada2a8f4ca2ee9b))

## [0.5.2](https://github.com/Daffaariff/hospital-chatbot/compare/v0.5.1...v0.5.2) (2026-11-10)


### Bug Fixes

* claim check sees full retrieved context; async parallel evals; lock index access ([2ded23d](https://github.com/Daffaariff/hospital-chatbot/commit/2ded23d88b77ada198b3591844a37eef431e8ed8))

## [0.5.1](https://github.com/Daffaariff/hospital-chatbot/compare/v0.5.0...v0.5.1) (2026-11-10)


### Bug Fixes

* let the claim check accept direct inferences and corrections ([9036d65](https://github.com/Daffaariff/hospital-chatbot/commit/9036d65a0052d8b6686309638b548db611c8afe8))

## [0.5.0](https://github.com/Daffaariff/hospital-chatbot/compare/v0.4.1...v0.5.0) (2026-11-10)


### Features

* support OpenRouter models without JSON-schema output and rewrite answer prompt ([6f72812](https://github.com/Daffaariff/hospital-chatbot/commit/6f72812c47e61c80d129638d63320da070d91cce))

## [0.4.1](https://github.com/Daffaariff/hospital-chatbot/compare/v0.4.0...v0.4.1) (2026-11-10)


### Bug Fixes

* answer comparisons directly instead of leading with caveats ([fb0f21e](https://github.com/Daffaariff/hospital-chatbot/commit/fb0f21e54be1c7d12bd4ae10de2bea6b68925eaa))

## [0.4.0](https://github.com/Daffaariff/hospital-chatbot/compare/v0.3.1...v0.4.0) (2026-11-10)


### Features

* stream answers over websocket with per-sentence number checks ([c7ec682](https://github.com/Daffaariff/hospital-chatbot/commit/c7ec682f90ad53e2c64e60d7f9285441f7d69a51))

## [0.3.1](https://github.com/Daffaariff/hospital-chatbot/compare/v0.3.0...v0.3.1) (2026-11-10)


### Bug Fixes

* per-claim verdicts and page titles for the claim check ([8ec6cd2](https://github.com/Daffaariff/hospital-chatbot/commit/8ec6cd22ffb2fd2303cc496b1b3f3a5937ecb656))

## [0.3.0](https://github.com/Daffaariff/hospital-chatbot/compare/v0.2.2...v0.3.0) (2026-11-10)


### Features

* check all numeric facts in code and add claim-level grounding check ([898e503](https://github.com/Daffaariff/hospital-chatbot/commit/898e503e77a5f073fe6cc5e6c100bee3b5230d9b))

## [0.2.2](https://github.com/Daffaariff/hospital-chatbot/compare/v0.2.1...v0.2.2) (2026-11-10)


### Bug Fixes

* keep FAQ questions, detect heading changes, resync index on start ([0713029](https://github.com/Daffaariff/hospital-chatbot/commit/0713029abf84ed606d2994ad52567f51fc495b96))

## [0.2.1](https://github.com/Daffaariff/hospital-chatbot/compare/v0.2.0...v0.2.1) (2026-11-10)


### Bug Fixes

* hold requests in caddy during app restarts ([ceba1fb](https://github.com/Daffaariff/hospital-chatbot/commit/ceba1fb75d1d4d9c0560dc27d1b28ceabb61bb65))

## [0.2.0](https://github.com/Daffaariff/hospital-chatbot/compare/v0.1.0...v0.2.0) (2026-11-10)


### Features

* grounded RAG chatbot for PlacidWay pages with CI/CD ([a73fc91](https://github.com/Daffaariff/hospital-chatbot/commit/a73fc91e3098ba96e5e0777590cb1ac4a09c0cd5))


### Bug Fixes

* embed in small batches to fit 2 GB server ([74581f5](https://github.com/Daffaariff/hospital-chatbot/commit/74581f56b076f87beb2f68703313b1aff3099d08))
* fuse user wording into retrieval and check prices against headings ([d75ed32](https://github.com/Daffaariff/hospital-chatbot/commit/d75ed323c8ed622b2adceba5bcdc58b1ebb40113))
