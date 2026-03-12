import { motion } from 'motion/react';
import { GitBranch, Folder, HardDrive, History, Shield, ArrowRight } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';

const capabilityCards = [
  {
    title: 'Project Registry',
    description: 'Register local workspaces, source paths and ownership rules before we wire the backend.',
    icon: Folder,
    accent: 'from-sky-500 to-cyan-500',
  },
  {
    title: 'Version Timeline',
    description: 'Track snapshots, restore points and release labels for each project from a single page.',
    icon: History,
    accent: 'from-violet-500 to-fuchsia-500',
  },
  {
    title: 'Storage Targets',
    description: 'Prepare retention and backup flows for local disk, archive storage and external destinations.',
    icon: HardDrive,
    accent: 'from-emerald-500 to-teal-500',
  },
];

const roadmap = [
  'Connect local project folders and capture metadata.',
  'Add version snapshots, diffs and recovery actions.',
  'Introduce storage policies and sync/backup automation.',
];

export function ProjectsPage() {
  const { theme, isDarkMode } = useTheme();
  const themeColors = getThemeColors(theme);

  return (
    <div className="animate-fade-in pb-12 space-y-8">
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)] gap-6">
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className={`relative overflow-hidden rounded-[2rem] border p-8 ${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'}`}
        >
          <div className={`absolute inset-0 bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} opacity-10`} />
          <div className="relative z-10 max-w-2xl">
            <div className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.24em] ${isDarkMode ? 'border-white/10 bg-white/5 text-gray-300' : 'border-gray-200 bg-gray-50 text-gray-600'}`}>
              <GitBranch size={14} />
              Projects
            </div>
            <h1 className={`mt-5 text-4xl font-bold bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
              Version control and project storage starts here
            </h1>
            <p className={`mt-4 max-w-xl text-base leading-7 ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
              This tab is the foundation for managing local project folders, version snapshots and storage policies directly from the panel.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <div className={`rounded-2xl border px-4 py-3 ${isDarkMode ? 'border-white/10 bg-white/5' : 'border-gray-200 bg-gray-50'}`}>
                <p className={`text-[11px] uppercase tracking-[0.22em] ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>Phase</p>
                <p className={`mt-2 text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>UI scaffold</p>
              </div>
              <div className={`rounded-2xl border px-4 py-3 ${isDarkMode ? 'border-white/10 bg-white/5' : 'border-gray-200 bg-gray-50'}`}>
                <p className={`text-[11px] uppercase tracking-[0.22em] ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>Next backend focus</p>
                <p className={`mt-2 text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Folder registration</p>
              </div>
            </div>
          </div>
        </motion.section>

        <motion.aside
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08 }}
          className={`rounded-[2rem] border p-6 ${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'}`}
        >
          <div className="flex items-center gap-3">
            <div className={`flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} text-white shadow-lg`}>
              <Shield size={22} />
            </div>
            <div>
              <p className={`text-sm font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Planned operating model</p>
              <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Controlled, reversible and storage-aware.</p>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            {roadmap.map((item, index) => (
              <div
                key={item}
                className={`flex items-start gap-3 rounded-2xl border p-4 ${isDarkMode ? 'border-white/10 bg-white/[0.03]' : 'border-gray-200 bg-gray-50'}`}
              >
                <div className={`mt-0.5 flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${isDarkMode ? 'bg-white/10 text-white' : 'bg-white text-gray-700 border border-gray-200'}`}>
                  {index + 1}
                </div>
                <div>
                  <p className={`text-sm font-medium ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{item}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.aside>
      </div>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {capabilityCards.map((card, index) => {
          const Icon = card.icon;

          return (
            <motion.article
              key={card.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12 + index * 0.06 }}
              className={`group rounded-[2rem] border p-6 ${isDarkMode ? 'bg-black/40 border-white/10 hover:border-white/20' : 'bg-white border-gray-200 shadow-sm hover:border-gray-300'} transition-all`}
            >
              <div className={`flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br ${card.accent} text-white shadow-lg`}>
                <Icon size={24} />
              </div>
              <h2 className={`mt-5 text-xl font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{card.title}</h2>
              <p className={`mt-3 text-sm leading-6 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{card.description}</p>
              <div className={`mt-6 inline-flex items-center gap-2 text-sm font-medium ${isDarkMode ? 'text-gray-300 group-hover:text-white' : 'text-gray-600 group-hover:text-gray-900'} transition-colors`}>
                Planned scope
                <ArrowRight size={16} />
              </div>
            </motion.article>
          );
        })}
      </section>
    </div>
  );
}
