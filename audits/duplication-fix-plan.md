# Code Duplication Fix Execution Plan
**Date:** 2025-11-18
**Status:** Ready for Execution

## Scope: Critical to Medium Priority Fixes

Fixing 11 issues with combined importance ≥6/10, targeting ~350 lines of reduction.

---

## Execution Order (Easiest → Hardest)

### Phase 1: Data Consolidation (2.5 hours, ~60 lines)
**Low Risk, High Impact**

#### 1. Fix 4.2: Field Name Constants ✓
- **Files:** `api/field_constants.py`, `config/field_manager.py`
- **Action:** Move DEFAULT_MINIMAL_FIELDS and DEFAULT_BALANCED_FIELDS to field_manager.py, import in field_constants.py
- **Impact:** Single source of truth for field lists
- **Risk:** Low (no behavior change)
- **Time:** 1 hour
- **Lines Saved:** 30

#### 2. Fix 4.3: Configuration Defaults ✓
- **Files:** `config/constants.py`, `config/settings.py`
- **Action:** Centralize all defaults in constants.py, reference in Settings class
- **Impact:** Single source of truth for configuration
- **Risk:** Low (no behavior change)
- **Time:** 1 hour
- **Lines Saved:** 15

#### 3. Fix 1.3: Cache Statistics ✓
- **Files:** `util/cache.py`
- **Action:** Create CacheStatsMixin, inherit in both TTLCache and LRUCache
- **Impact:** Remove duplicate get_stats() methods
- **Risk:** Low (pure refactor)
- **Time:** 30 minutes
- **Lines Saved:** 24

---

### Phase 2: Core Utilities (4 hours, ~155 lines)
**Medium Risk, High Impact**

#### 4. Fix 1.1: HTTP Error Handling ✓
- **Files:** `shared/error_utils.py`, `api/enriched_client.py`
- **Action:** Create raise_http_exception() in error_utils, simplify _handle_http_error()
- **Impact:** Centralized HTTP error handling
- **Risk:** Medium (critical path)
- **Time:** 1 hour
- **Lines Saved:** 45

#### 5. Fix 2.3: Field Filtering Logic ✓
- **Files:** `config/field_manager.py`, `main.py`
- **Action:** Add filter_response_custom() and filter_response_smart() to FieldManager
- **Impact:** Remove duplicate filtering code in main.py
- **Risk:** Medium (used in tools)
- **Time:** 1 hour
- **Lines Saved:** 30

#### 6. Fix 2.2: Query Validation ✓
- **Files:** `util/query_validator.py` (create), `api/enriched_client.py`, `api/client.py`
- **Action:** Create comprehensive query validator module
- **Impact:** Centralized query validation
- **Risk:** Medium (validation logic)
- **Time:** 2 hours
- **Lines Saved:** 80

---

### Phase 3: Advanced Patterns (4 hours, ~60 lines)
**Medium Risk, Code Quality**

#### 7. Fix 3.2: Parameter Validation ✓
- **Files:** `util/validators.py` (create), `main.py`
- **Action:** Create Validator class with chainable validation
- **Impact:** Reusable validation patterns
- **Risk:** Medium (validation logic)
- **Time:** 2 hours
- **Lines Saved:** 30

#### 8. Fix 2.1: Deprecate Old API Client ✓
- **Files:** `api/client.py`, `main.py`
- **Action:** Add deprecation warnings to client.py, update main.py to use enriched_client only
- **Impact:** Remove 522 lines of legacy code (deprecation path)
- **Risk:** Medium (API surface)
- **Time:** 2 hours
- **Lines Saved:** Prepare for removal (522 lines in next version)

---

### Phase 4: Additional Medium Priority (Optional, if time permits)

#### 9. Fix 3.1: Singleton Pattern
- **Files:** `util/singleton.py` (create), update all singleton implementations
- **Time:** 3 hours
- **Lines Saved:** 50

#### 10. Fix 1.2: Retry Decorator Logic
- **Files:** `util/retry.py`
- **Time:** 2 hours
- **Lines Saved:** 80

#### 11. Fix 4.1: Exception Status Code Mapping
- **Files:** `shared/exceptions.py`, `shared/error_utils.py`
- **Time:** 2 hours
- **Lines Saved:** 50

---

## Testing Strategy

### After Each Fix:
1. **Syntax Check:** Ensure code runs without import errors
2. **Spot Test:** Test specific functionality modified
3. **Commit:** Small, atomic commits for easy rollback

### After All Fixes:
1. **Unit Tests:** Run existing test suite
2. **Integration Tests:** Test tool functions
3. **Import Tests:** Verify all imports resolve
4. **Regression Check:** Ensure no behavior changes

---

## Risk Mitigation

### For Each Change:
- ✅ Read existing code first
- ✅ Create backup with git commits
- ✅ Test incrementally
- ✅ Document changes clearly
- ✅ Keep diff small and focused

### Rollback Plan:
- Each fix is a separate commit
- Can revert individual commits if issues arise
- Branch allows safe experimentation

---

## Success Criteria

### Phase 1 Complete:
- [ ] All data duplications resolved
- [ ] Single source of truth for fields and config
- [ ] ~60 lines removed
- [ ] All tests pass

### Phase 2 Complete:
- [ ] Core utilities centralized
- [ ] HTTP error handling unified
- [ ] Query validation consolidated
- [ ] ~215 lines removed total
- [ ] All tests pass

### Phase 3 Complete:
- [ ] Advanced patterns implemented
- [ ] Old client deprecated
- [ ] ~245 lines removed total
- [ ] All tests pass

---

## Estimated Timeline

- **Phase 1:** 2.5 hours (Data Consolidation)
- **Phase 2:** 4 hours (Core Utilities)
- **Phase 3:** 4 hours (Advanced Patterns)
- **Testing & Validation:** 1 hour
- **Total:** 11.5 hours

---

## Current Status: READY TO EXECUTE

**Next Action:** Start with Fix 4.2 (Field Name Constants)
