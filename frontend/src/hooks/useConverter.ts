"use client";

/**
 * Owns the whole conversion workflow as an explicit state machine:
 *
 *   idle -> uploading -> uploaded -> converting -> completed | failed
 *
 * All network access goes through `@/lib/api`; this hook only manages state,
 * polling and cleanup. Polling stops as soon as the component unmounts or a
 * job reaches a terminal state.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "@/lib/api";
import type {
  ConversionJob,
  FormatsPayload,
  UploadedFile,
  UserFacingError,
  WorkflowState,
} from "@/types";

const POLL_INTERVAL_MS = 700;
const MAX_POLL_ATTEMPTS = 2000;

export interface ConverterActions {
  formats: FormatsPayload | null;
  formatsError: UserFacingError | null;
  isLoadingFormats: boolean;
  state: WorkflowState;
  file: UploadedFile | null;
  job: ConversionJob | null;
  targetFormat: string;
  error: UserFacingError | null;
  isDragActive: boolean;
  setTargetFormat: (format: string) => void;
  setDragActive: (active: boolean) => void;
  handleFile: (file: File) => Promise<void>;
  startConversion: () => Promise<void>;
  download: () => Promise<void>;
  reset: () => void;
}

function toUserFacing(error: unknown): UserFacingError {
  if (error instanceof ApiError) return error.code;
  return "unknown";
}

export function useConverter(): ConverterActions {
  const [formats, setFormats] = useState<FormatsPayload | null>(null);
  const [formatsError, setFormatsError] = useState<UserFacingError | null>(null);
  const [isLoadingFormats, setIsLoadingFormats] = useState(true);

  const [state, setState] = useState<WorkflowState>("idle");
  const [file, setFile] = useState<UploadedFile | null>(null);
  const [job, setJob] = useState<ConversionJob | null>(null);
  const [targetFormat, setTargetFormat] = useState("");
  const [error, setError] = useState<UserFacingError | null>(null);
  const [isDragActive, setDragActive] = useState(false);

  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, []);

  // Load the format matrix once - the backend is the source of truth.
  useEffect(() => {
    let cancelled = false;

    api
      .formats()
      .then((payload) => {
        if (cancelled || !mounted.current) return;
        setFormats(payload);
        setFormatsError(null);
      })
      .catch((cause: unknown) => {
        if (cancelled || !mounted.current) return;
        setFormatsError(toUserFacing(cause));
      })
      .finally(() => {
        if (!cancelled && mounted.current) setIsLoadingFormats(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  const failWith = useCallback((cause: unknown) => {
    setError(toUserFacing(cause));
    setState("failed");
    setJob(null);
  }, []);

  const pollJob = useCallback(
    (jobId: string, attempt = 0) => {
      if (attempt > MAX_POLL_ATTEMPTS) {
        if (mounted.current) {
          setError("server_error");
          setState("failed");
        }
        return;
      }

      api
        .getConversion(jobId)
        .then((current) => {
          if (!mounted.current) return;
          setJob(current);

          if (current.status === "completed") {
            setState("completed");
            return;
          }
          if (current.status === "failed") {
            setError("conversion_failed");
            setState("failed");
            return;
          }
          pollTimer.current = setTimeout(
            () => pollJob(jobId, attempt + 1),
            POLL_INTERVAL_MS,
          );
        })
        .catch((cause: unknown) => {
          if (!mounted.current) return;
          // A transient poll failure is not fatal while the job is still running.
          if (attempt < 5) {
            pollTimer.current = setTimeout(
              () => pollJob(jobId, attempt + 1),
              POLL_INTERVAL_MS * 2,
            );
            return;
          }
          failWith(cause);
        });
    },
    [failWith],
  );

  const handleFile = useCallback(
    async (selected: File) => {
      stopPolling();
      setError(null);
      setJob(null);
      setTargetFormat("");
      setState("uploading");
      setFile(null);

      try {
        const uploaded = await api.upload(selected);
        if (!mounted.current) return;
        setFile(uploaded);
        setTargetFormat(uploaded.available_formats[0] ?? "");
        setState("uploaded");
      } catch (cause) {
        if (!mounted.current) return;
        failWith(cause);
      }
    },
    [failWith, stopPolling],
  );

  const startConversion = useCallback(async () => {
    if (!file || !targetFormat) return;
    stopPolling();
    setError(null);
    setState("converting");

    try {
      const started = await api.startConversion(file.id, targetFormat);
      if (!mounted.current) return;
      setJob(started);
      if (started.status === "completed") {
        setState("completed");
        return;
      }
      if (started.status === "failed") {
        setError("conversion_failed");
        setState("failed");
        return;
      }
      pollJob(started.id);
    } catch (cause) {
      if (!mounted.current) return;
      failWith(cause);
    }
  }, [failWith, file, pollJob, stopPolling, targetFormat]);

  const download = useCallback(async () => {
    if (!job || job.status !== "completed" || !job.output_name) return;
    try {
      await api.download(job.id, job.output_name);
    } catch (cause) {
      if (!mounted.current) return;
      failWith(cause);
    }
  }, [failWith, job]);

  const reset = useCallback(() => {
    stopPolling();

    // Best-effort server-side cleanup; the retention sweeper covers failures.
    if (file) void api.deleteFile(file.id).catch(() => undefined);
    if (job) void api.deleteConversion(job.id).catch(() => undefined);

    setFile(null);
    setJob(null);
    setTargetFormat("");
    setError(null);
    setState("idle");
  }, [file, job, stopPolling]);

  return {
    formats,
    formatsError,
    isLoadingFormats,
    state,
    file,
    job,
    targetFormat,
    error,
    isDragActive,
    setTargetFormat,
    setDragActive,
    handleFile,
    startConversion,
    download,
    reset,
  };
}
