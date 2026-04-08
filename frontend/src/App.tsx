import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Upload, Link as LinkIcon, Download, Search, Play, Pause, FastForward, Rewind, Activity } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type JobStatus = 'pending' | 'processing' | 'complete' | 'error';

interface Job {
  id: string;
  status: JobStatus;
  progress: number;
  step: string;
  error?: string;
}

interface Timecode {
  start: string;
  end: string;
  start_seconds: number;
  end_seconds: number;
  duration: number;
  scene_number: number;
  type: string;
  description: string;
  dialogue_excerpt: string;
  thumbnail_url: string;
}

const tagColors: Record<string, string> = {
  DIALOGUE: 'bg-tag-dialogue text-white',
  ACTION: 'bg-tag-action text-white',
  FIGHT: 'bg-tag-fight text-white',
  CHASE: 'bg-tag-chase text-white',
  EXPLOSION: 'bg-tag-explosion text-white',
  ROMANCE: 'bg-tag-romance text-white',
  COMEDY: 'bg-tag-comedy text-gray-900',
  DRAMA: 'bg-tag-drama text-white',
  TRANSITION: 'bg-tag-transition text-white',
  MONTAGE: 'bg-tag-montage text-white',
  CREDITS: 'bg-tag-credits text-white',
  SILENCE: 'bg-tag-silence text-gray-900',
  UNKNOWN: 'bg-gray-600 text-white',
};

function getTagColor(tag: string) {
  return tagColors[tag?.toUpperCase()] || tagColors.UNKNOWN;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [timecodes, setTimecodes] = useState<Timecode[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [search, setSearch] = useState('');

  const videoRef = useRef<HTMLVideoElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    if (!job || job.status === 'complete' || job.status === 'error') return;

    const sse = new EventSource(`/api/jobs/${job.id}/stream`);

    sse.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.error && !data.step) {
        setJob(prev => prev ? { ...prev, status: 'error', error: data.error } : null);
        sse.close();
        return;
      }

      setJob(prev => prev ? {
        ...prev,
        status: data.status,
        progress: data.progress,
        step: data.step,
        error: data.error
      } : null);

      if (data.status === 'complete') {
        sse.close();
        fetchTimecodes(job.id);
      } else if (data.status === 'error') {
        sse.close();
      }
    };

    sse.onerror = () => {
      sse.close();
    };

    return () => sse.close();
  }, [job?.id, job?.status]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file && !videoUrl) return;

    setIsUploading(true);
    const formData = new FormData();
    if (file) formData.append('file', file);
    if (videoUrl) formData.append('video_url', videoUrl);

    try {
      const res = await axios.post('/api/analyze', formData);
      setJob({ id: res.data.job_id, status: 'pending', progress: 0, step: 'Starting...' });
      setTimecodes([]);
    } catch (err) {
      console.error(err);
      alert('Upload failed.');
    } finally {
      setIsUploading(false);
    }
  };

  const fetchTimecodes = async (jobId: string) => {
    try {
      const res = await axios.get(`/api/jobs/${jobId}/timecodes`);
      setTimecodes(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const seekTo = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play();
    }
  };

  const activeSceneIndex = timecodes.findIndex(tc =>
    currentTime >= tc.start_seconds && currentTime < tc.end_seconds
  );

  useEffect(() => {
    if (activeSceneIndex !== -1 && listRef.current) {
      const element = document.getElementById(`scene-${activeSceneIndex}`);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [activeSceneIndex]);

  const filteredTimecodes = timecodes.filter(tc =>
    tc.type.toLowerCase().includes(search.toLowerCase()) ||
    tc.description.toLowerCase().includes(search.toLowerCase()) ||
    tc.dialogue_excerpt?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-surface p-4 flex items-center justify-between sticky top-0 z-10 bg-background">
        <div className="flex items-center gap-2">
          <Activity className="text-primary w-6 h-6" />
          <h1 className="text-xl font-bold tracking-tight">CineTimecode</h1>
        </div>

        {job?.status === 'complete' && (
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input
                type="text"
                placeholder="Search scenes..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-9 pr-4 py-1.5 bg-surface rounded-full text-sm focus:outline-none focus:ring-1 focus:ring-primary w-64"
              />
            </div>
            <div className="flex items-center gap-2">
              <a href={`/api/jobs/${job.id}/export?format=json`} className="p-1.5 hover:bg-surface rounded-md text-text-muted hover:text-white" title="Export JSON">
                <Download className="w-5 h-5" />
              </a>
              <a href={`/api/jobs/${job.id}/export?format=csv`} className="p-1.5 hover:bg-surface rounded-md text-text-muted hover:text-white" title="Export CSV">
                <span className="text-xs font-bold font-mono">CSV</span>
              </a>
              <a href={`/api/jobs/${job.id}/export?format=txt`} className="p-1.5 hover:bg-surface rounded-md text-text-muted hover:text-white" title="Export TXT">
                <span className="text-xs font-bold font-mono">TXT</span>
              </a>
            </div>
          </div>
        )}
      </header>

      <main className="flex-1 flex overflow-hidden">
        {!job ? (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="max-w-md w-full bg-surface p-8 rounded-xl shadow-2xl border border-surface-hover">
              <h2 className="text-2xl font-semibold mb-6 text-center">Analyze Video</h2>

              <form onSubmit={handleUpload} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-text-muted mb-2">Upload File</label>
                  <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-surface-hover hover:border-primary/50 rounded-lg cursor-pointer bg-background/50 transition-colors">
                    <div className="flex flex-col items-center justify-center pt-5 pb-6">
                      <Upload className="w-8 h-8 mb-3 text-text-muted" />
                      <p className="mb-2 text-sm text-text-muted">
                        <span className="font-semibold text-primary">Click to upload</span> or drag and drop
                      </p>
                      <p className="text-xs text-text-muted">MP4, MKV, MOV, AVI</p>
                    </div>
                    <input
                      type="file"
                      className="hidden"
                      accept="video/*"
                      onChange={e => setFile(e.target.files?.[0] || null)}
                    />
                  </label>
                  {file && <p className="mt-2 text-sm text-center text-primary">{file.name}</p>}
                </div>

                <div className="relative flex items-center py-2">
                  <div className="flex-grow border-t border-surface-hover"></div>
                  <span className="flex-shrink-0 mx-4 text-text-muted text-sm">OR</span>
                  <div className="flex-grow border-t border-surface-hover"></div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-text-muted mb-2">Video URL</label>
                  <div className="relative">
                    <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                    <input
                      type="url"
                      placeholder="https://youtube.com/..."
                      value={videoUrl}
                      onChange={e => setVideoUrl(e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 bg-background border border-surface-hover rounded-lg focus:outline-none focus:border-primary transition-colors"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isUploading || (!file && !videoUrl)}
                  className="w-full bg-primary hover:bg-primary/90 text-gray-900 font-semibold py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isUploading ? 'Uploading...' : 'Start Analysis'}
                </button>
              </form>
            </div>
          </div>
        ) : job.status !== 'complete' ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8">
             <div className="max-w-md w-full bg-surface p-8 rounded-xl shadow-2xl border border-surface-hover text-center">
                <Activity className="w-12 h-12 text-primary mx-auto mb-6 animate-pulse" />
                <h2 className="text-xl font-semibold mb-2">Analyzing Video</h2>
                <p className="text-text-muted mb-8">{job.step || 'Initializing pipeline...'}</p>

                <div className="w-full bg-background rounded-full h-2 mb-4 overflow-hidden">
                  <div
                    className="bg-primary h-2 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${job.progress}%` }}
                  ></div>
                </div>
                <div className="text-sm text-text-muted text-right">{job.progress}%</div>

                {job.status === 'error' && (
                  <div className="mt-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm text-left">
                    <p className="font-semibold mb-1">Error occurred:</p>
                    <p>{job.error}</p>
                  </div>
                )}
             </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
            {/* Left Panel: Video */}
            <div className="w-full md:w-1/2 lg:w-3/5 bg-black flex flex-col border-r border-surface">
              <div className="flex-1 relative flex items-center justify-center">
                <video
                  ref={videoRef}
                  src={`/api/jobs/${job.id}/video`}
                  className="w-full h-full object-contain"
                  onTimeUpdate={handleTimeUpdate}
                  onLoadedMetadata={handleLoadedMetadata}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  controls
                />
              </div>

              {/* Timeline Visualization */}
              <div className="h-12 bg-surface border-t border-surface-hover relative overflow-hidden group cursor-pointer"
                   onClick={(e) => {
                     if (!videoRef.current || !duration) return;
                     const rect = e.currentTarget.getBoundingClientRect();
                     const x = e.clientX - rect.left;
                     const percentage = x / rect.width;
                     seekTo(percentage * duration);
                   }}>
                {duration > 0 && timecodes.map((tc, i) => {
                  const left = (tc.start_seconds / duration) * 100;
                  const width = (tc.duration / duration) * 100;
                  return (
                    <div
                      key={i}
                      className={cn("absolute h-full opacity-70 hover:opacity-100 transition-opacity border-r border-surface/20", getTagColor(tc.type))}
                      style={{ left: `${left}%`, width: `${width}%` }}
                      title={`${tc.type}: ${tc.description}`}
                    />
                  );
                })}
                {/* Scrubber head */}
                {duration > 0 && (
                  <div
                    className="absolute top-0 bottom-0 w-0.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] z-10 pointer-events-none"
                    style={{ left: `${(currentTime / duration) * 100}%` }}
                  />
                )}
              </div>
            </div>

            {/* Right Panel: Timecodes */}
            <div className="w-full md:w-1/2 lg:w-2/5 flex flex-col bg-background">
              <div className="p-4 border-b border-surface flex justify-between items-center bg-surface">
                <h3 className="font-semibold">Scene Analysis</h3>
                <span className="text-xs text-text-muted bg-background px-2 py-1 rounded-md">
                  {filteredTimecodes.length} scenes
                </span>
              </div>

              <div ref={listRef} className="flex-1 overflow-y-auto p-4 space-y-4">
                {filteredTimecodes.map((tc, i) => {
                  const isActive = activeSceneIndex === timecodes.indexOf(tc);
                  return (
                    <div
                      key={i}
                      id={`scene-${timecodes.indexOf(tc)}`}
                      className={cn(
                        "flex gap-4 p-3 rounded-xl border transition-all cursor-pointer group",
                        isActive
                          ? "bg-surface border-primary/50 shadow-lg"
                          : "bg-surface/50 border-surface-hover hover:border-surface-hover hover:bg-surface"
                      )}
                      onClick={() => seekTo(tc.start_seconds)}
                    >
                      <div className="w-32 h-20 shrink-0 bg-background rounded-lg overflow-hidden relative border border-surface-hover">
                        {tc.thumbnail_url ? (
                          <img src={tc.thumbnail_url} className="w-full h-full object-cover" alt={`Scene ${tc.scene_number}`} />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-text-muted text-xs">No image</div>
                        )}
                        <div className="absolute bottom-1 right-1 bg-black/80 text-[10px] px-1.5 py-0.5 rounded text-white backdrop-blur-sm">
                          {tc.duration.toFixed(1)}s
                        </div>
                      </div>

                      <div className="flex-1 min-w-0 flex flex-col">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-mono text-text-muted group-hover:text-primary transition-colors">
                            {tc.start} &rarr; {tc.end}
                          </span>
                          <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded-sm tracking-wide", getTagColor(tc.type))}>
                            {tc.type}
                          </span>
                        </div>
                        <p className="text-sm text-text mb-2 line-clamp-2 leading-relaxed">
                          {tc.description}
                        </p>
                        {tc.dialogue_excerpt && (
                          <div className="mt-auto">
                            <p className="text-xs text-text-muted italic border-l-2 border-surface-hover pl-2 line-clamp-1">
                              "{tc.dialogue_excerpt}"
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
                {filteredTimecodes.length === 0 && (
                  <div className="text-center py-12 text-text-muted">
                    No scenes found matching your search.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
