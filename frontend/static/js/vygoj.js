// Execution status enumeration
export var Status;
(function (Status) {
  Status["pending"] = "pending";
  Status["passed"] = "passed";
  Status["wrong"] = "wrong";
  Status["timeout"] = "timeout";
  Status["compilerError"] = "compilerError";
  Status["runtimeError"] = "runtimeError";
  Status["internalError"] = "internalError";
})(Status || (Status = {}));
;
