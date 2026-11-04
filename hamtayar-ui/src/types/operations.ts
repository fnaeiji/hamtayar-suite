export type OperationMode = 'demo' | 'api';

export type OperationStatus =
  | 'idle'
  | 'validating'
  | 'pending'
  | 'completed'
  | 'failed'
  | 'uncertain';

export type ResultProvenance = 'fixture' | 'service' | 'none';

export type DiagnosticErrorKind =
  | 'timeout'
  | 'network'
  | 'http'
  | 'invalid_response'
  | 'aborted'
  | 'blocked';

export type SanitizedDiagnostic = {
  kind: DiagnosticErrorKind;
  message: string;
  statusCode?: number;
  requestId?: string;
  elapsedMs?: number;
};

export type OperationRecord<TResult = unknown> = {
  id: string;
  generation: number;
  mode: OperationMode;
  status: OperationStatus;
  provenance: ResultProvenance;
  startedAt: number;
  updatedAt: number;
  result?: TResult;
  diagnostic?: SanitizedDiagnostic;
};

export type OperationUpdate<TResult = unknown> = Partial<
  Pick<OperationRecord<TResult>, 'status' | 'provenance' | 'result' | 'diagnostic'>
>;
