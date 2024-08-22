  var __create = Object.create;
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __getProtoOf = Object.getPrototypeOf;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __commonJS = (cb, mod) => function __require() {
    return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
    // If the importer is in node compatibility mode or this is not an ESM
    // file that has been converted to a CommonJS file using a Babel-
    // compatible transform (i.e. "__esModule" has not been set), then set
    // "default" to the CommonJS "module.exports" for node compatibility.
    isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
    mod
  ));

  // ../../lex/lexer.js
  var require_lexer = __commonJS({
    "../../lex/lexer.js"(exports, module) {
      if (typeof module === "object" && typeof module.exports === "object") module.exports = Lexer2;
      Lexer2.defunct = function(chr) {
        throw new Error("Unexpected character at index " + (this.index - 1) + ": " + chr);
      };
      function Lexer2(defunct) {
        if (typeof defunct !== "function") defunct = Lexer2.defunct;
        var tokens = [];
        var rules = [];
        var remove = 0;
        this.state = 0;
        this.index = 0;
        this.input = "";
        this.addRule = function(pattern, action, start) {
          var global2 = pattern.global;
          if (!global2) {
            var flags = "g";
            if (pattern.multiline) flags += "m";
            if (pattern.ignoreCase) flags += "i";
            pattern = new RegExp(pattern.source, flags);
          }
          if (Object.prototype.toString.call(start) !== "[object Array]") start = [0];
          rules.push({
            pattern,
            global: global2,
            action,
            start
          });
          return this;
        };
        this.setInput = function(input) {
          remove = 0;
          this.state = 0;
          this.index = 0;
          tokens.length = 0;
          this.input = input;
          return this;
        };
        this.lex = function() {
          if (tokens.length) return tokens.shift();
          this.reject = true;
          while (this.index <= this.input.length) {
            var matches = scan.call(this).splice(remove);
            var index = this.index;
            while (matches.length) {
              if (this.reject) {
                var match = matches.shift();
                var result = match.result;
                var length = match.length;
                this.index += length;
                this.reject = false;
                remove++;
                var token2 = match.action.apply(this, result);
                if (this.reject) this.index = result.index;
                else if (typeof token2 !== "undefined") {
                  switch (Object.prototype.toString.call(token2)) {
                    case "[object Array]":
                      tokens = token2.slice(1);
                      token2 = token2[0];
                    default:
                      if (length) remove = 0;
                      return token2;
                  }
                }
              } else break;
            }
            var input = this.input;
            if (index < input.length) {
              if (this.reject) {
                remove = 0;
                var token2 = defunct.call(this, input.charAt(this.index++));
                if (typeof token2 !== "undefined") {
                  if (Object.prototype.toString.call(token2) === "[object Array]") {
                    tokens = token2.slice(1);
                    return token2[0];
                  } else return token2;
                }
              } else {
                if (this.index !== index) remove = 0;
                this.reject = true;
              }
            } else if (matches.length)
              this.reject = true;
            else break;
          }
        };
        function scan() {
          var matches = [];
          var index = 0;
          var state = this.state;
          var lastIndex = this.index;
          var input = this.input;
          for (var i = 0, length = rules.length; i < length; i++) {
            var rule = rules[i];
            var start = rule.start;
            var states = start.length;
            if (!states || start.indexOf(state) >= 0 || state % 2 && states === 1 && !start[0]) {
              var pattern = rule.pattern;
              pattern.lastIndex = lastIndex;
              var result = pattern.exec(input);
              if (result && result.index === lastIndex) {
                var j = matches.push({
                  result,
                  action: rule.action,
                  length: result[0].length
                });
                if (rule.global) index = j;
                while (--j > index) {
                  var k = j - 1;
                  if (matches[j].length > matches[k].length) {
                    var temple = matches[j];
                    matches[j] = matches[k];
                    matches[k] = temple;
                  }
                }
              }
            }
          }
          return matches;
        }
      }
    }
  });

  // ../../lodash/isObject.js
  var require_isObject = __commonJS({
    "../../lodash/isObject.js"(exports, module) {
      function isObject2(value) {
        var type = typeof value;
        return value != null && (type == "object" || type == "function");
      }
      module.exports = isObject2;
    }
  });

  // ../../lodash/_freeGlobal.js
  var require_freeGlobal = __commonJS({
    "../../lodash/_freeGlobal.js"(exports, module) {
      var freeGlobal = typeof global == "object" && global && global.Object === Object && global;
      module.exports = freeGlobal;
    }
  });

  // ../../lodash/_root.js
  var require_root = __commonJS({
    "../../lodash/_root.js"(exports, module) {
      var freeGlobal = require_freeGlobal();
      var freeSelf = typeof self == "object" && self && self.Object === Object && self;
      var root = freeGlobal || freeSelf || Function("return this")();
      module.exports = root;
    }
  });

  // ../../lodash/now.js
  var require_now = __commonJS({
    "../../lodash/now.js"(exports, module) {
      var root = require_root();
      var now = function() {
        return root.Date.now();
      };
      module.exports = now;
    }
  });

  // ../../lodash/_trimmedEndIndex.js
  var require_trimmedEndIndex = __commonJS({
    "../../lodash/_trimmedEndIndex.js"(exports, module) {
      var reWhitespace = /\s/;
      function trimmedEndIndex(string) {
        var index = string.length;
        while (index-- && reWhitespace.test(string.charAt(index))) {
        }
        return index;
      }
      module.exports = trimmedEndIndex;
    }
  });

  // ../../lodash/_baseTrim.js
  var require_baseTrim = __commonJS({
    "../../lodash/_baseTrim.js"(exports, module) {
      var trimmedEndIndex = require_trimmedEndIndex();
      var reTrimStart = /^\s+/;
      function baseTrim(string) {
        return string ? string.slice(0, trimmedEndIndex(string) + 1).replace(reTrimStart, "") : string;
      }
      module.exports = baseTrim;
    }
  });

  // ../../lodash/_Symbol.js
  var require_Symbol = __commonJS({
    "../../lodash/_Symbol.js"(exports, module) {
      var root = require_root();
      var Symbol2 = root.Symbol;
      module.exports = Symbol2;
    }
  });

  // ../../lodash/_getRawTag.js
  var require_getRawTag = __commonJS({
    "../../lodash/_getRawTag.js"(exports, module) {
      var Symbol2 = require_Symbol();
      var objectProto = Object.prototype;
      var hasOwnProperty = objectProto.hasOwnProperty;
      var nativeObjectToString = objectProto.toString;
      var symToStringTag = Symbol2 ? Symbol2.toStringTag : void 0;
      function getRawTag(value) {
        var isOwn = hasOwnProperty.call(value, symToStringTag), tag = value[symToStringTag];
        try {
          value[symToStringTag] = void 0;
          var unmasked = true;
        } catch (e) {
        }
        var result = nativeObjectToString.call(value);
        if (unmasked) {
          if (isOwn) {
            value[symToStringTag] = tag;
          } else {
            delete value[symToStringTag];
          }
        }
        return result;
      }
      module.exports = getRawTag;
    }
  });

  // ../../lodash/_objectToString.js
  var require_objectToString = __commonJS({
    "../../lodash/_objectToString.js"(exports, module) {
      var objectProto = Object.prototype;
      var nativeObjectToString = objectProto.toString;
      function objectToString(value) {
        return nativeObjectToString.call(value);
      }
      module.exports = objectToString;
    }
  });

  // ../../lodash/_baseGetTag.js
  var require_baseGetTag = __commonJS({
    "../../lodash/_baseGetTag.js"(exports, module) {
      var Symbol2 = require_Symbol();
      var getRawTag = require_getRawTag();
      var objectToString = require_objectToString();
      var nullTag = "[object Null]";
      var undefinedTag = "[object Undefined]";
      var symToStringTag = Symbol2 ? Symbol2.toStringTag : void 0;
      function baseGetTag(value) {
        if (value == null) {
          return value === void 0 ? undefinedTag : nullTag;
        }
        return symToStringTag && symToStringTag in Object(value) ? getRawTag(value) : objectToString(value);
      }
      module.exports = baseGetTag;
    }
  });

  // ../../lodash/isObjectLike.js
  var require_isObjectLike = __commonJS({
    "../../lodash/isObjectLike.js"(exports, module) {
      function isObjectLike(value) {
        return value != null && typeof value == "object";
      }
      module.exports = isObjectLike;
    }
  });

  // ../../lodash/isSymbol.js
  var require_isSymbol = __commonJS({
    "../../lodash/isSymbol.js"(exports, module) {
      var baseGetTag = require_baseGetTag();
      var isObjectLike = require_isObjectLike();
      var symbolTag = "[object Symbol]";
      function isSymbol(value) {
        return typeof value == "symbol" || isObjectLike(value) && baseGetTag(value) == symbolTag;
      }
      module.exports = isSymbol;
    }
  });

  // ../../lodash/toNumber.js
  var require_toNumber = __commonJS({
    "../../lodash/toNumber.js"(exports, module) {
      var baseTrim = require_baseTrim();
      var isObject2 = require_isObject();
      var isSymbol = require_isSymbol();
      var NAN = 0 / 0;
      var reIsBadHex = /^[-+]0x[0-9a-f]+$/i;
      var reIsBinary = /^0b[01]+$/i;
      var reIsOctal = /^0o[0-7]+$/i;
      var freeParseInt = parseInt;
      function toNumber(value) {
        if (typeof value == "number") {
          return value;
        }
        if (isSymbol(value)) {
          return NAN;
        }
        if (isObject2(value)) {
          var other = typeof value.valueOf == "function" ? value.valueOf() : value;
          value = isObject2(other) ? other + "" : other;
        }
        if (typeof value != "string") {
          return value === 0 ? value : +value;
        }
        value = baseTrim(value);
        var isBinary = reIsBinary.test(value);
        return isBinary || reIsOctal.test(value) ? freeParseInt(value.slice(2), isBinary ? 2 : 8) : reIsBadHex.test(value) ? NAN : +value;
      }
      module.exports = toNumber;
    }
  });

  // ../../lodash/debounce.js
  var require_debounce = __commonJS({
    "../../lodash/debounce.js"(exports, module) {
      var isObject2 = require_isObject();
      var now = require_now();
      var toNumber = require_toNumber();
      var FUNC_ERROR_TEXT = "Expected a function";
      var nativeMax = Math.max;
      var nativeMin = Math.min;
      function debounce2(func, wait, options) {
        var lastArgs, lastThis, maxWait, result, timerId, lastCallTime, lastInvokeTime = 0, leading = false, maxing = false, trailing = true;
        if (typeof func != "function") {
          throw new TypeError(FUNC_ERROR_TEXT);
        }
        wait = toNumber(wait) || 0;
        if (isObject2(options)) {
          leading = !!options.leading;
          maxing = "maxWait" in options;
          maxWait = maxing ? nativeMax(toNumber(options.maxWait) || 0, wait) : maxWait;
          trailing = "trailing" in options ? !!options.trailing : trailing;
        }
        function invokeFunc(time) {
          var args = lastArgs, thisArg = lastThis;
          lastArgs = lastThis = void 0;
          lastInvokeTime = time;
          result = func.apply(thisArg, args);
          return result;
        }
        function leadingEdge(time) {
          lastInvokeTime = time;
          timerId = setTimeout(timerExpired, wait);
          return leading ? invokeFunc(time) : result;
        }
        function remainingWait(time) {
          var timeSinceLastCall = time - lastCallTime, timeSinceLastInvoke = time - lastInvokeTime, timeWaiting = wait - timeSinceLastCall;
          return maxing ? nativeMin(timeWaiting, maxWait - timeSinceLastInvoke) : timeWaiting;
        }
        function shouldInvoke(time) {
          var timeSinceLastCall = time - lastCallTime, timeSinceLastInvoke = time - lastInvokeTime;
          return lastCallTime === void 0 || timeSinceLastCall >= wait || timeSinceLastCall < 0 || maxing && timeSinceLastInvoke >= maxWait;
        }
        function timerExpired() {
          var time = now();
          if (shouldInvoke(time)) {
            return trailingEdge(time);
          }
          timerId = setTimeout(timerExpired, remainingWait(time));
        }
        function trailingEdge(time) {
          timerId = void 0;
          if (trailing && lastArgs) {
            return invokeFunc(time);
          }
          lastArgs = lastThis = void 0;
          return result;
        }
        function cancel() {
          if (timerId !== void 0) {
            clearTimeout(timerId);
          }
          lastInvokeTime = 0;
          lastArgs = lastCallTime = lastThis = timerId = void 0;
        }
        function flush() {
          return timerId === void 0 ? result : trailingEdge(now());
        }
        function debounced() {
          var time = now(), isInvoking = shouldInvoke(time);
          lastArgs = arguments;
          lastThis = this;
          lastCallTime = time;
          if (isInvoking) {
            if (timerId === void 0) {
              return leadingEdge(lastCallTime);
            }
            if (maxing) {
              clearTimeout(timerId);
              timerId = setTimeout(timerExpired, wait);
              return invokeFunc(lastCallTime);
            }
          }
          if (timerId === void 0) {
            timerId = setTimeout(timerExpired, wait);
          }
          return result;
        }
        debounced.cancel = cancel;
        debounced.flush = flush;
        return debounced;
      }
      module.exports = debounce2;
    }
  });

  // ../../lodash/throttle.js
  var require_throttle = __commonJS({
    "../../lodash/throttle.js"(exports, module) {
      var debounce2 = require_debounce();
      var isObject2 = require_isObject();
      var FUNC_ERROR_TEXT = "Expected a function";
      function throttle2(func, wait, options) {
        var leading = true, trailing = true;
        if (typeof func != "function") {
          throw new TypeError(FUNC_ERROR_TEXT);
        }
        if (isObject2(options)) {
          leading = "leading" in options ? !!options.leading : leading;
          trailing = "trailing" in options ? !!options.trailing : trailing;
        }
        return debounce2(func, wait, {
          "leading": leading,
          "maxWait": wait,
          "trailing": trailing
        });
      }
      module.exports = throttle2;
    }
  });

  // index.js
  var import_lex = __toESM(require_lexer());
  var import_debounce = __toESM(require_debounce());
  var import_isObject = __toESM(require_isObject());
  var import_throttle = __toESM(require_throttle());

  // lru-cache.js
  function LRUCache(limit) {
    this.size = 0;
    this.limit = limit;
    this.oldest = this.newest = void 0;
    this._keymap = {};
  }
  LRUCache.prototype._markEntryAsUsed = function(entry) {
    if (entry === this.newest) {
      return;
    }
    if (entry.newer) {
      if (entry === this.oldest) {
        this.oldest = entry.newer;
      }
      entry.newer.older = entry.older;
    }
    if (entry.older) {
      entry.older.newer = entry.newer;
    }
    entry.newer = void 0;
    entry.older = this.newest;
    if (this.newest) {
      this.newest.newer = entry;
    }
    this.newest = entry;
  };
  LRUCache.prototype.put = function(key, value) {
    var entry = this._keymap[key];
    if (entry) {
      entry.value = value;
      this._markEntryAsUsed(entry);
      return;
    }
    this._keymap[key] = entry = { key, value, older: void 0, newer: void 0 };
    if (this.newest) {
      this.newest.newer = entry;
      entry.older = this.newest;
    } else {
      this.oldest = entry;
    }
    this.newest = entry;
    this.size++;
    if (this.size > this.limit) {
      return this.shift();
    }
  };
  LRUCache.prototype.shift = function() {
    var entry = this.oldest;
    if (entry) {
      if (this.oldest.newer) {
        this.oldest = this.oldest.newer;
        this.oldest.older = void 0;
      } else {
        this.oldest = void 0;
        this.newest = void 0;
      }
      entry.newer = entry.older = void 0;
      delete this._keymap[entry.key];
      this.size--;
    }
    return entry;
  };
  LRUCache.prototype.get = function(key, returnEntry) {
    var entry = this._keymap[key];
    if (entry === void 0) return;
    this._markEntryAsUsed(entry);
    return returnEntry ? entry : entry.value;
  };
  LRUCache.prototype.find = function(key) {
    return this._keymap[key];
  };
  LRUCache.prototype.set = function(key, value) {
    var oldvalue, entry = this.get(key, true);
    if (entry) {
      oldvalue = entry.value;
      entry.value = value;
    } else {
      oldvalue = this.put(key, value);
      if (oldvalue) oldvalue = oldvalue.value;
    }
    return oldvalue;
  };
  LRUCache.prototype.remove = function(key) {
    var entry = this._keymap[key];
    if (!entry) return;
    delete this._keymap[entry.key];
    if (entry.newer && entry.older) {
      entry.older.newer = entry.newer;
      entry.newer.older = entry.older;
    } else if (entry.newer) {
      entry.newer.older = void 0;
      this.oldest = entry.newer;
    } else if (entry.older) {
      entry.older.newer = void 0;
      this.newest = entry.older;
    } else {
      this.oldest = this.newest = void 0;
    }
    this.size--;
    return entry.value;
  };
  LRUCache.prototype.removeAll = function() {
    this.oldest = this.newest = void 0;
    this.size = 0;
    this._keymap = {};
  };
  if (typeof Object.keys === "function") {
    LRUCache.prototype.keys = function() {
      return Object.keys(this._keymap);
    };
  } else {
    LRUCache.prototype.keys = function() {
      var keys = [];
      for (var k in this._keymap) {
        keys.push(k);
      }
      return keys;
    };
  }
  LRUCache.prototype.forEach = function(fun, context, desc) {
    var entry;
    if (context === true) {
      desc = true;
      context = void 0;
    } else if (typeof context !== "object") {
      context = this;
    }
    if (desc) {
      entry = this.newest;
      while (entry) {
        fun.call(context, entry.key, entry.value, this);
        entry = entry.older;
      }
    } else {
      entry = this.oldest;
      while (entry) {
        fun.call(context, entry.key, entry.value, this);
        entry = entry.newer;
      }
    }
  };
  LRUCache.prototype.toJSON = function() {
    var s = new Array(this.size), i = 0, entry = this.oldest;
    while (entry) {
      s[i++] = { key: entry.key, value: entry.value };
      entry = entry.newer;
    }
    return s;
  };
  LRUCache.prototype.toString = function() {
    var s = "", entry = this.oldest;
    while (entry) {
      s += String(entry.key) + ":" + entry.value;
      entry = entry.newer;
      if (entry) {
        s += " < ";
      }
    }
    return s;
  };
  var lru_cache_default = LRUCache;

  // utils.js
  function DOMReady(callback) {
    if (document.readyState !== "loading") {
      callback();
    } else {
      document.addEventListener("DOMContentLoaded", callback);
    }
  }
  function setUrlParams(url, params) {
    const parts = url.split("?");
    const path = parts[0];
    let queryString = parts.slice(1).join("?");
    const pairs = queryString.split("&");
    let pair;
    let key;
    let value;
    let i;
    Object.keys(params).forEach((k) => {
      key = encodeURI(k);
      value = encodeURI(params[key]);
      i = pairs.length;
      while (i--) {
        pair = pairs[i].split("=");
        if (pair[0] === key) {
          pair[1] = value;
          pairs[i] = pair.join("=");
          break;
        }
      }
      if (i < 0) {
        pairs.push(`${key}=${value}`);
      }
    });
    queryString = pairs.join("&");
    return queryString ? [path, queryString].join("?") : path;
  }
  function escapeRegExp(str) {
    return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, "\\$&");
  }

  // index.js
  var reIntValue = "(-?0|-?[1-9][0-9]*)";
  var reFractionPart = "\\.[0-9]+";
  var reExponentPart = "[eE][+-]?[0-9]+";
  var intRegex = new RegExp(reIntValue);
  var floatRegex = new RegExp(
    `${reIntValue}${reFractionPart}${reExponentPart}|${reIntValue}${reFractionPart}|${reIntValue}${reExponentPart}`
  );
  var reLineTerminators = "\\n\\r\\u2028\\u2029";
  var reEscapedChar = '\\\\[\\\\"/bfnrt]';
  var reEscapedUnicode = "\\\\u[0-9A-Fa-f]{4}";
  var reStringChar = `[^\\\\"\\\\\\\\${reLineTerminators}]`;
  var stringRegex = new RegExp(
    `\\"(${reEscapedChar}|${reEscapedUnicode}|${reStringChar})*\\"`
  );
  var nameRegex = /[_A-Za-z][_0-9A-Za-z]*(\.[_A-Za-z][_0-9A-Za-z]*)*/;
  var reNotFollowedByName = "(?![_0-9A-Za-z])";
  var whitespaceRegex = /[ \t\v\f\u00A0]+/;
  var lexer = new import_lex.default(() => {
  });
  function token(name, value) {
    return { name, value };
  }
  lexer.addRule(whitespaceRegex, () => {
  });
  lexer.addRule(/\./, (l) => token("DOT", l));
  lexer.addRule(/,/, (l) => token("COMMA", l));
  lexer.addRule(new RegExp(`or${reNotFollowedByName}`), (l) => token("OR", l));
  lexer.addRule(new RegExp(`and${reNotFollowedByName}`), (l) => token("AND", l));
  lexer.addRule(new RegExp(`not${reNotFollowedByName}`), (l) => token("NOT", l));
  lexer.addRule(new RegExp(`in${reNotFollowedByName}`), (l) => token("IN", l));
  lexer.addRule(
    new RegExp(`startswith${reNotFollowedByName}`),
    (l) => token("STARTSWITH", l)
  );
  lexer.addRule(
    new RegExp(`endswith${reNotFollowedByName}`),
    (l) => token("ENDSWITH", l)
  );
  lexer.addRule(
    new RegExp(`True${reNotFollowedByName}`),
    (l) => token("TRUE", l)
  );
  lexer.addRule(
    new RegExp(`False${reNotFollowedByName}`),
    (l) => token("FALSE", l)
  );
  lexer.addRule(
    new RegExp(`None${reNotFollowedByName}`),
    (l) => token("NONE", l)
  );
  lexer.addRule(nameRegex, (l) => token("NAME", l));
  lexer.addRule(
    stringRegex,
    // Trim leading and trailing quotes:
    (l) => token("STRING_VALUE", l.slice(1, l.length - 1))
  );
  lexer.addRule(intRegex, (l) => token("INT_VALUE", l));
  lexer.addRule(floatRegex, (l) => token("FLOAT_VALUE", l));
  lexer.addRule(/\(/, (l) => token("PAREN_L", l));
  lexer.addRule(/\)/, (l) => token("PAREN_R", l));
  lexer.addRule(/=/, (l) => token("EQUALS", l));
  lexer.addRule(/!=/, (l) => token("NOT_EQUALS", l));
  lexer.addRule(/>/, (l) => token("GREATER", l));
  lexer.addRule(/>=/, (l) => token("GREATER_EQUAL", l));
  lexer.addRule(/</, (l) => token("LESS", l));
  lexer.addRule(/<=/, (l) => token("LESS_EQUAL", l));
  lexer.addRule(/~/, (l) => token("CONTAINS", l));
  lexer.addRule(/!~/, (l) => token("NOT_CONTAINS", l));
  lexer.lexAll = function() {
    let match;
    const result = [];
    while (match = this.lex()) {
      match.start = this.index - match.value.length;
      match.end = this.index;
      result.push(match);
    }
    return result;
  };
  function suggestion(text, snippetBefore, snippetAfter, explanation) {
    let suggestionText = text;
    if (typeof explanation !== "undefined") {
      suggestionText += `<i>${explanation}</i>`;
    }
    return {
      text,
      snippetBefore: snippetBefore || "",
      snippetAfter: snippetAfter || "",
      suggestionText
    };
  }
  var DjangoQL = function(options) {
    let cacheSize = 100;
    this.options = options;
    this.currentModel = null;
    this.models = {};
    this.suggestionsAPIUrl = null;
    this.token = token;
    this.lexer = lexer;
    this.prefix = "";
    this.suggestions = [];
    this.selected = null;
    this.valuesCaseSensitive = false;
    this.highlightCaseSensitive = true;
    this.textarea = null;
    this.completion = null;
    this.completionUL = null;
    this.completionEnabled = false;
    if (!(0, import_isObject.default)(options)) {
      this.logError("Please pass an object with initialization parameters");
      return;
    }
    this.loadIntrospections(options.introspections);
    if (typeof options.selector === "string") {
      this.textarea = document.querySelector(options.selector);
    } else {
      this.textarea = options.selector;
    }
    if (!this.textarea) {
      this.logError(`Element not found by selector: ${options.selector}`);
      return;
    }
    if (this.textarea.tagName !== "TEXTAREA") {
      this.logError(
        `selector must be pointing to <textarea> element, but ${this.textarea.tagName} was found`
      );
      return;
    }
    if (options.valuesCaseSensitive) {
      this.valuesCaseSensitive = true;
    }
    if (options.cacheSize) {
      if (parseInt(options.cacheSize, 10) !== options.cacheSize || options.cacheSize < 1) {
        this.logError("cacheSize must be a positive integer");
      } else {
        cacheSize = options.cacheSize;
      }
    }
    this.suggestionsCache = new lru_cache_default(cacheSize);
    this.debouncedLoadFieldOptions = (0, import_debounce.default)(
      this.loadFieldOptions.bind(this),
      300
    );
    this.loading = false;
    this.enableCompletion = this.enableCompletion.bind(this);
    this.disableCompletion = this.disableCompletion.bind(this);
    this.onCompletionMouseClick = this.onCompletionMouseClick.bind(this);
    this.onCompletionMouseDown = this.onCompletionMouseDown.bind(this);
    this.popupCompletion = this.popupCompletion.bind(this);
    this.debouncedRenderCompletion = (0, import_debounce.default)(
      this.renderCompletion.bind(this),
      50
    );
    this.textarea.setAttribute("autocomplete", "off");
    this.textarea.addEventListener("keydown", this.onKeydown.bind(this));
    this.textarea.addEventListener("blur", this.hideCompletion.bind(this));
    this.textarea.addEventListener("click", this.popupCompletion);
    if (options.autoResize) {
      this.textareaResize = this.textareaResize.bind(this);
      this.textarea.style.resize = "none";
      this.textarea.style.overflow = "hidden";
      this.textarea.addEventListener("input", this.textareaResize);
      this.textareaResize();
      window.addEventListener("load", this.textareaResize);
    } else {
      this.textareaResize = null;
      this.textarea.addEventListener(
        "mouseup",
        this.renderCompletion.bind(this, true)
      );
      this.textarea.addEventListener(
        "mouseout",
        this.renderCompletion.bind(this, true)
      );
    }
    this.createCompletionElement();
  };
  DjangoQL.init = function(options) {
    return new DjangoQL(options);
  };
  DjangoQL.DOMReady = DOMReady;
  DjangoQL.prototype = {
    createCompletionElement() {
      const { options } = this;
      let syntaxHelp;
      if (!this.completion) {
        this.completion = document.createElement("div");
        this.completion.className = "djangoql-completion";
        document.querySelector("body").appendChild(this.completion);
        this.completionUL = document.createElement("ul");
        this.completionUL.onscroll = (0, import_throttle.default)(
          this.onCompletionScroll.bind(this),
          50
        );
        this.completion.appendChild(this.completionUL);
        if (typeof options.syntaxHelp === "string") {
          syntaxHelp = document.createElement("p");
          syntaxHelp.className = "syntax-help";
          syntaxHelp.innerHTML = `<a href="${options.syntaxHelp}" target="_blank">Syntax Help</a>`;
          syntaxHelp.addEventListener("mousedown", (e) => {
            e.preventDefault();
          });
          this.completion.appendChild(syntaxHelp);
        }
        this.completionEnabled = options.hasOwnProperty("completionEnabled") ? options.completionEnabled : true;
      }
    },
    destroyCompletionElement() {
      if (this.completion) {
        this.completion.parentNode.removeChild(this.completion);
        this.completion = null;
        this.completionEnabled = false;
      }
    },
    enableCompletion() {
      this.completionEnabled = true;
    },
    disableCompletion() {
      this.completionEnabled = false;
      this.hideCompletion();
    },
    getJson(url, settings) {
      this.loading = true;
      const onLoadError = function() {
        this.loading = false;
        this.request = null;
        this.logError(`failed to fetch from ${url}`);
      }.bind(this);
      if (this.request) {
        this.request.abort();
      }
      this.request = new XMLHttpRequest();
      this.request.open("GET", url, true);
      this.request.onload = function() {
        this.loading = false;
        if (this.request.status === 200) {
          if (typeof settings.success === "function") {
            settings.success(JSON.parse(this.request.responseText));
          }
        } else {
          onLoadError();
        }
        this.request = null;
      }.bind(this);
      this.request.ontimeout = onLoadError;
      this.request.onerror = onLoadError;
      this.request.onprogress = function() {
      };
      window.setTimeout(this.request.send.bind(this.request));
    },
    loadIntrospections(introspections) {
      const initIntrospections = function(data) {
        this.currentModel = data.current_model;
        this.models = data.models;
        this.suggestionsAPIUrl = data.suggestions_api_url;
      }.bind(this);
      if (typeof introspections === "string") {
        this.getJson(introspections, { success: initIntrospections });
      } else if ((0, import_isObject.default)(introspections)) {
        initIntrospections(introspections);
      } else {
        this.logError(
          `introspections parameter is expected to be either URL or object with definitions, but ${introspections} was found`
        );
      }
    },
    logError(message) {
      console.error(`DjangoQL: ${message}`);
    },
    onCompletionMouseClick(e) {
      this.selectCompletion(
        parseInt(e.currentTarget.getAttribute("data-index"), 10)
      );
    },
    onCompletionMouseDown(e) {
      e.preventDefault();
    },
    onKeydown(e) {
      switch (e.keyCode) {
        case 38:
          if (this.suggestions.length) {
            if (this.selected === null) {
              this.selected = this.suggestions.length - 1;
            } else if (this.selected === 0) {
              this.selected = null;
            } else {
              this.selected -= 1;
            }
            this.renderCompletion();
            e.preventDefault();
          }
          break;
        case 40:
          if (this.suggestions.length) {
            if (this.selected === null) {
              this.selected = 0;
            } else if (this.selected < this.suggestions.length - 1) {
              this.selected += 1;
            } else {
              this.selected = null;
            }
            this.renderCompletion();
            e.preventDefault();
          }
          break;
        case 9:
          if (this.selected !== null) {
            this.selectCompletion(this.selected);
            e.preventDefault();
          }
          break;
        case 13:
          if (this.selected !== null) {
            this.selectCompletion(this.selected);
          } else if (typeof this.options.onSubmit === "function") {
            this.options.onSubmit(this.textarea.value);
          } else {
            e.currentTarget.form.submit();
          }
          e.preventDefault();
          break;
        case 27:
          this.hideCompletion();
          break;
        case 16:
        case 17:
        case 18:
        case 91:
        case 93:
          break;
        default:
          window.setTimeout(this.popupCompletion, 10);
          break;
      }
    },
    textareaResize() {
      const style = window.getComputedStyle(this.textarea, null);
      const heightOffset = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      this.textarea.style.height = "5px";
      const height = this.textarea.scrollHeight - heightOffset + 1;
      this.textarea.style.height = `${height}px`;
    },
    popupCompletion() {
      this.generateSuggestions();
      this.renderCompletion();
    },
    selectCompletion(index) {
      const context = this.getContext(
        this.textarea.value,
        this.textarea.selectionStart
      );
      const { currentFullToken } = context;
      let textValue = this.textarea.value;
      const startPos = this.textarea.selectionStart - context.prefix.length;
      let tokenEndPos = null;
      if (currentFullToken) {
        tokenEndPos = currentFullToken.end;
        textValue = textValue.slice(0, startPos) + textValue.slice(tokenEndPos);
      }
      const textBefore = textValue.slice(0, startPos);
      let textAfter = textValue.slice(startPos);
      textAfter = textAfter.trim();
      const completion = this.suggestions[index];
      let { snippetBefore, snippetAfter } = completion;
      const snippetAfterParts = snippetAfter.split("|");
      if (snippetAfterParts.length > 1) {
        snippetAfter = snippetAfterParts.join("");
        if (!snippetBefore && !completion.text) {
          [snippetBefore, snippetAfter] = snippetAfterParts;
        }
      }
      if (textBefore.endsWith(snippetBefore)) {
        snippetBefore = "";
      }
      if (textAfter.startsWith(snippetAfter)) {
        snippetAfter = "";
      }
      const textToPaste = snippetBefore + completion.text + snippetAfter;
      let cursorPosAfter = textBefore.length + textToPaste.length;
      if (snippetAfterParts.length > 1) {
        cursorPosAfter -= snippetAfterParts[1].length;
      }
      this.textarea.value = textBefore + textToPaste + textAfter;
      this.textarea.focus();
      this.textarea.setSelectionRange(cursorPosAfter, cursorPosAfter);
      this.selected = null;
      if (this.textareaResize) {
        this.textareaResize();
      }
      this.generateSuggestions(this.textarea);
      this.renderCompletion();
    },
    hideCompletion() {
      this.selected = null;
      if (this.completion) {
        this.completion.style.display = "none";
      }
    },
    highlight(text, highlight) {
      if (!highlight || !text) {
        return text;
      }
      if (this.highlightCaseSensitive) {
        return text.split(highlight).join(`<b>${highlight}</b>`);
      }
      return text.replace(
        new RegExp(`(${escapeRegExp(highlight)})`, "ig"),
        "<b>$1</b>"
      );
    },
    renderCompletion(dontForceDisplay) {
      let currentLi;
      let i;
      let completionRect;
      let currentLiRect;
      let liLen;
      let loadingElement;
      if (!this.completionEnabled) {
        this.hideCompletion();
        return;
      }
      if (dontForceDisplay && this.completion.style.display === "none") {
        return;
      }
      if (!this.suggestions.length && !this.loading) {
        this.hideCompletion();
        return;
      }
      const suggestionsLen = this.suggestions.length;
      const li = [].slice.call(
        this.completionUL.querySelectorAll("li[data-index]")
      );
      liLen = li.length;
      for (i = 0; i < suggestionsLen; i++) {
        if (i < liLen) {
          currentLi = li[i];
        } else {
          currentLi = document.createElement("li");
          currentLi.setAttribute("data-index", i);
          currentLi.addEventListener("click", this.onCompletionMouseClick);
          currentLi.addEventListener("mousedown", this.onCompletionMouseDown);
          this.completionUL.appendChild(currentLi);
        }
        currentLi.innerHTML = this.highlight(
          this.suggestions[i].suggestionText,
          this.prefix
        );
        if (i === this.selected) {
          currentLi.className = "active";
          currentLiRect = currentLi.getBoundingClientRect();
          completionRect = this.completionUL.getBoundingClientRect();
          if (currentLiRect.bottom > completionRect.bottom) {
            this.completionUL.scrollTop = this.completionUL.scrollTop + 2 + (currentLiRect.bottom - completionRect.bottom);
          } else if (currentLiRect.top < completionRect.top) {
            this.completionUL.scrollTop = this.completionUL.scrollTop - 2 - (completionRect.top - currentLiRect.top);
          }
        } else {
          currentLi.className = "";
        }
      }
      while (liLen > suggestionsLen) {
        liLen--;
        li[liLen].removeEventListener("click", this.onCompletionMouseClick);
        li[liLen].removeEventListener("mousedown", this.onCompletionMouseDown);
        this.completionUL.removeChild(li[liLen]);
      }
      loadingElement = this.completionUL.querySelector("li.djangoql-loading");
      if (this.loading) {
        if (!loadingElement) {
          loadingElement = document.createElement("li");
          loadingElement.className = "djangoql-loading";
          loadingElement.innerHTML = "&nbsp;";
          this.completionUL.appendChild(loadingElement);
        }
      } else if (loadingElement) {
        this.completionUL.removeChild(loadingElement);
      }
      const inputRect = this.textarea.getBoundingClientRect();
      const top = window.pageYOffset + inputRect.top + inputRect.height;
      this.completion.style.top = `${top}px`;
      this.completion.style.left = `${inputRect.left}px`;
      this.completion.style.display = "block";
    },
    resolveName(name) {
      let f;
      let i;
      let l;
      const nameParts = name.split(".");
      let model = this.currentModel;
      let field = null;
      const modelStack = [];
      if (model) {
        modelStack.push(model);
        for (i = 0, l = nameParts.length; i < l; i++) {
          f = this.models[model][nameParts[i]];
          if (!f) {
            model = null;
            field = null;
            break;
          } else if (f.type === "relation") {
            model = f.relation;
            modelStack.push(model);
            field = null;
          } else {
            field = nameParts[i];
          }
        }
      }
      return { modelStack, model, field };
    },
    getContext(text, cursorPos) {
      let prefix;
      let scope = null;
      let model = null;
      let field = null;
      let modelStack = [this.currentModel];
      let nameParts;
      let resolvedName;
      let lastToken = null;
      let nextToLastToken = null;
      const tokens = this.lexer.setInput(text.slice(0, cursorPos)).lexAll();
      const allTokens = this.lexer.setInput(text).lexAll();
      let currentFullToken = null;
      if (tokens.length && tokens[tokens.length - 1].end >= cursorPos) {
        currentFullToken = allTokens[tokens.length - 1];
        tokens.pop();
      }
      if (tokens.length) {
        lastToken = tokens[tokens.length - 1];
        if (tokens.length > 1) {
          nextToLastToken = tokens[tokens.length - 2];
        }
      }
      prefix = text.slice(lastToken ? lastToken.end : 0, cursorPos);
      const whitespace = prefix.match(whitespaceRegex);
      if (whitespace) {
        prefix = prefix.slice(whitespace[0].length);
      }
      if (prefix === "(") {
        prefix = "";
      }
      const logicalTokens = ["AND", "OR"];
      if (prefix === ")" && !whitespace) {
      } else if (!lastToken || logicalTokens.indexOf(lastToken.name) >= 0 && whitespace || prefix === "." && lastToken && !whitespace || lastToken.name === "PAREN_L" && (!nextToLastToken || logicalTokens.indexOf(nextToLastToken.name) >= 0)) {
        scope = "field";
        model = this.currentModel;
        if (prefix === ".") {
          prefix = text.slice(lastToken.start, cursorPos);
        }
        nameParts = prefix.split(".");
        if (nameParts.length > 1) {
          prefix = nameParts.pop();
          resolvedName = this.resolveName(nameParts.join("."));
          if (resolvedName.model && !resolvedName.field) {
            model = resolvedName.model;
            modelStack = resolvedName.modelStack;
          } else {
            scope = null;
            model = null;
          }
        }
      } else if (lastToken && whitespace && nextToLastToken && nextToLastToken.name === "NAME" && [
        "EQUALS",
        "NOT_EQUALS",
        "CONTAINS",
        "NOT_CONTAINS",
        "GREATER_EQUAL",
        "GREATER",
        "LESS_EQUAL",
        "LESS"
      ].indexOf(lastToken.name) >= 0) {
        resolvedName = this.resolveName(nextToLastToken.value);
        if (resolvedName.model) {
          scope = "value";
          model = resolvedName.model;
          field = resolvedName.field;
          modelStack = resolvedName.modelStack;
          if (prefix[0] === '"' && (this.models[model][field].type === "str" || this.models[model][field].options)) {
            prefix = prefix.slice(1);
          }
        }
      } else if (lastToken && whitespace && lastToken.name === "NAME") {
        resolvedName = this.resolveName(lastToken.value);
        if (resolvedName.model) {
          scope = "comparison";
          model = resolvedName.model;
          field = resolvedName.field;
          modelStack = resolvedName.modelStack;
        }
      } else if (lastToken && whitespace && ["PAREN_R", "INT_VALUE", "FLOAT_VALUE", "STRING_VALUE"].indexOf(lastToken.name) >= 0) {
        scope = "logical";
      }
      return {
        prefix,
        scope,
        model,
        field,
        currentFullToken,
        modelStack
      };
    },
    getCurrentFieldOptions() {
      const input = this.textarea;
      const ctx = this.getContext(input.value, input.selectionStart);
      const model = this.models[ctx.model];
      const field = ctx.field && model[ctx.field];
      const fieldOptions = {
        cacheKey: null,
        context: ctx,
        field,
        model,
        options: null
      };
      if (ctx.scope !== "value" || !field || !field.options) {
        return null;
      }
      if (Array.isArray(field.options)) {
        fieldOptions.options = field.options;
      } else if (field.options === true) {
        if (!this.suggestionsAPIUrl) {
          return null;
        }
        fieldOptions.cacheKey = `${ctx.model}.${ctx.field}|${ctx.prefix}`;
      }
      return fieldOptions;
    },
    loadFieldOptions(loadMore) {
      const fieldOptions = this.getCurrentFieldOptions() || {};
      const { context } = fieldOptions;
      if (!fieldOptions.cacheKey) {
        return;
      }
      const requestParams = {
        field: `${context.model}.${context.field}`,
        search: context.prefix
      };
      const cached = this.suggestionsCache.get(fieldOptions.cacheKey) || {};
      if (loadMore && cached.has_next) {
        requestParams.page = cached.page ? cached.page + 1 : 1;
      } else if (cached.page) {
        return;
      }
      cached.loading = true;
      this.suggestionsCache.set(fieldOptions.cacheKey, cached);
      const requestUrl = setUrlParams(this.suggestionsAPIUrl, requestParams);
      this.getJson(requestUrl, {
        success: function(data) {
          const cache = this.suggestionsCache.get(fieldOptions.cacheKey) || {};
          if (data.page - 1 !== (cache.page || 0)) {
            return;
          }
          const cachedData = {
            ...data,
            items: (cache.items || []).concat(data.items)
          };
          this.suggestionsCache.set(fieldOptions.cacheKey, cachedData);
          this.loading = false;
          this.populateFieldOptions();
          this.renderCompletion();
        }.bind(this)
      });
      this.populateFieldOptions();
      this.renderCompletion();
    },
    populateFieldOptions(loadMore) {
      const fieldOptions = this.getCurrentFieldOptions();
      if (fieldOptions === null) {
        return;
      }
      let { options } = fieldOptions;
      const prefix = fieldOptions.context && fieldOptions.context.prefix;
      let cached;
      if (options) {
        if (this.valuesCaseSensitive) {
          options = options.filter((item) => (
            // Case-sensitive
            item.indexOf(prefix) >= 0
          ));
        } else {
          options = options.filter((item) => (
            // Case-insensitive
            item.toLowerCase().indexOf(prefix.toLowerCase()) >= 0
          ));
        }
      } else {
        this.suggestions = [];
        if (!fieldOptions.cacheKey) {
          return;
        }
        cached = this.suggestionsCache.get(fieldOptions.cacheKey) || {};
        options = cached.items || [];
        if (!cached.loading && (!cached.page || loadMore && cached.has_next)) {
          this.debouncedLoadFieldOptions(loadMore);
        }
        if (!options.length) {
          return;
        }
      }
      this.highlightCaseSensitive = this.valuesCaseSensitive;
      this.suggestions = options.map((f) => suggestion(f, '"', '"'));
    },
    onCompletionScroll() {
      const rectHeight = this.completionUL.getBoundingClientRect().height;
      const scrollBottom = this.completionUL.scrollTop + rectHeight;
      if (scrollBottom > rectHeight && scrollBottom > this.completionUL.scrollHeight - rectHeight) {
        this.populateFieldOptions(true);
      }
    },
    generateSuggestions() {
      const input = this.textarea;
      let suggestions;
      let snippetAfter;
      let searchFilter;
      if (!this.completionEnabled) {
        this.prefix = "";
        this.suggestions = [];
        return;
      }
      if (!this.currentModel) {
        return;
      }
      if (input.selectionStart !== input.selectionEnd) {
        this.prefix = "";
        this.suggestions = [];
        return;
      }
      searchFilter = function(item) {
        return item.text.indexOf(this.prefix) >= 0;
      }.bind(this);
      this.highlightCaseSensitive = true;
      const context = this.getContext(input.value, input.selectionStart);
      const { modelStack } = context;
      this.prefix = context.prefix;
      const model = this.models[context.model];
      const field = context.field && model[context.field];
      switch (context.scope) {
        case "field":
          this.suggestions = Object.keys(model).filter((f) => {
            const { relation } = model[f];
            if (model[f].type === "relation" && modelStack.includes(relation) && modelStack.slice(-1)[0] !== relation) {
              return false;
            }
            return true;
          }).map((f) => suggestion(f, "", model[f].type === "relation" ? "." : " "));
          break;
        case "comparison":
          suggestions = ["=", ["!=", "is not equal to"]];
          snippetAfter = " ";
          if (field && field.type !== "bool") {
            if (["date", "datetime"].indexOf(field.type) >= 0) {
              suggestions.push(
                ["~", "contains"],
                ["!~", "does not contain"]
              );
              snippetAfter = ' "|"';
            } else if (field.type === "str") {
              suggestions.push(
                ["~", "contains"],
                ["!~", "does not contain"],
                "startswith",
                "not startswith",
                "endswith",
                "not endswith"
              );
              snippetAfter = ' "|"';
            } else if (field.options) {
              snippetAfter = ' "|"';
            }
            if (field.type !== "str") {
              suggestions.push(">", ">=", "<", "<=");
            }
          }
          this.suggestions = suggestions.map((s) => {
            if (typeof s === "string") {
              return suggestion(s, "", snippetAfter);
            }
            return suggestion(s[0], "", snippetAfter, s[1]);
          });
          if (field && field.type !== "bool") {
            if (["str", "date", "datetime"].indexOf(field.type) >= 0 || field.options) {
              snippetAfter = ' ("|")';
            } else {
              snippetAfter = " (|)";
            }
            this.suggestions.push(suggestion("in", "", snippetAfter));
            this.suggestions.push(suggestion("not in", "", snippetAfter));
          }
          searchFilter = function(item) {
            return item.text.lastIndexOf(this.prefix, 0) === 0;
          }.bind(this);
          break;
        case "value":
          if (!field) {
            this.suggestions = [suggestion("None", "", " ")];
          } else if (field.options) {
            this.prefix = context.prefix;
            this.populateFieldOptions();
          } else if (field.type === "bool") {
            this.suggestions = [
              suggestion("True", "", " "),
              suggestion("False", "", " ")
            ];
            if (field.nullable) {
              this.suggestions.push(suggestion("None", "", " "));
            }
          } else if (field.type === "unknown") {
            this.prefix = "";
            this.suggestions = [];
          }
          break;
        case "logical":
          this.suggestions = [
            suggestion("and", "", " "),
            suggestion("or", "", " ")
          ];
          break;
        default:
          this.prefix = "";
          this.suggestions = [];
      }
      this.suggestions = this.suggestions.filter(searchFilter);
      if (this.suggestions.length === 1) {
        this.selected = 0;
      } else {
        this.selected = null;
      }
    }
  };
  var src_default = DjangoQL;
