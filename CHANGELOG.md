# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- This changelog (3500a73)
- Endpoint GET /cameras/{mxid}/streams/{stream_name}/nn for retrieving running NN config (2a59f99)
- Endpoint POST /cameras/refresh for refreshing list of available cameras along with boot option (d0a0ac7)

### Changed

- Endpoint GET /cameras/{mxid}/streams now returns list of objects (StreamInfo) instead of a single object (550e269)

### Fixed

- Situation where app crashes on startup due to camera crash (663794a)
