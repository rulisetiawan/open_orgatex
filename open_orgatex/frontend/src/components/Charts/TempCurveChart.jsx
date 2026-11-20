import React from 'react';
import ReactApexChart from 'react-apexcharts';
import { useTheme } from '../../context/ThemeContext';

const TempCurveChart = ({ 
  series, 
  categories, 
  title = "Profil Kurva Suhu Pencelupan (°C)",
  height = 360 
}) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark' || (typeof document !== 'undefined' && document.documentElement.classList.contains('dark'));

  // SMM Automation refined industrial palette
  const chartColors = isDark 
    ? ['#f43f5e', '#38bdf8', '#10b981', '#fbbf24', '#a855f7'] 
    : ['#e11d48', '#2563eb', '#059669', '#d97706', '#7c3aed'];

  const options = {
    chart: {
      type: 'line',
      height: height,
      toolbar: {
        show: true,
        tools: {
          download: true,
          selection: true,
          zoom: true,
          zoomin: true,
          zoomout: true,
          pan: true,
          reset: true,
        },
      },
      zoom: { enabled: true },
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      background: 'transparent',
      dropShadow: {
        enabled: isDark ? false : true,
        color: '#000000',
        top: 4,
        blur: 4,
        left: 0,
        opacity: 0.04,
      },
      animations: {
        enabled: true,
        easing: 'easeinout',
        speed: 400,
        dynamicAnimation: {
          enabled: true,
          speed: 300,
        },
      },
    },
    theme: {
      mode: isDark ? 'dark' : 'light',
    },
    colors: chartColors,
    stroke: {
      width: [2.5, 2, 2, 1.8],
      curve: 'smooth',
      dashArray: [0, 4, 0, 2],
    },
    title: {
      text: title,
      align: 'left',
      style: {
        fontSize: '14px',
        fontWeight: 700,
        color: isDark ? '#eef4f6' : '#0f172a',
        fontFamily: "'Inter', sans-serif",
      },
    },
    grid: {
      borderColor: isDark ? '#1c2e42' : '#e2e8f0',
      strokeDashArray: 3,
      xaxis: { lines: { show: true } },
      yaxis: { lines: { show: true } },
      padding: {
        top: 10,
        right: 15,
        bottom: 5,
        left: 15,
      },
    },
    xaxis: {
      categories: categories || [],
      title: {
        text: 'Timeline / Langkah Resep',
        style: {
          fontSize: '11px',
          fontWeight: 600,
          color: isDark ? '#8b9eae' : '#64748b',
          fontFamily: "'Inter', sans-serif",
        },
      },
      labels: {
        style: {
          colors: isDark ? '#8b9eae' : '#64748b',
          fontSize: '11px',
          fontWeight: 500,
          fontFamily: "'Inter', sans-serif",
        },
      },
      axisBorder: {
        show: true,
        color: isDark ? '#1c2e42' : '#e2e8f0',
      },
      axisTicks: {
        show: true,
        color: isDark ? '#1c2e42' : '#e2e8f0',
      },
    },
    yaxis: {
      min: 20,
      max: 140,
      title: {
        text: 'Suhu (°C)',
        style: {
          fontSize: '11px',
          fontWeight: 600,
          color: isDark ? '#8b9eae' : '#64748b',
          fontFamily: "'Inter', sans-serif",
        },
      },
      labels: {
        formatter: (val) => `${Math.round(val)}°C`,
        style: {
          colors: isDark ? '#8b9eae' : '#64748b',
          fontSize: '11px',
          fontWeight: 500,
          fontFamily: "'Inter', sans-serif",
        },
      },
    },
    legend: {
      position: 'top',
      horizontalAlign: 'right',
      fontSize: '12px',
      fontWeight: 600,
      fontFamily: "'Inter', sans-serif",
      labels: {
        colors: isDark ? '#eef4f6' : '#0f172a',
      },
      markers: {
        radius: 4,
      },
      itemMargin: {
        horizontal: 8,
        vertical: 4,
      },
    },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      shared: true,
      intersect: false,
      style: {
        fontSize: '12px',
        fontFamily: "'Inter', sans-serif",
      },
      y: {
        formatter: (val) => (val !== undefined && val !== null ? `${val} °C` : '-'),
      },
    },
    markers: {
      size: 0,
      hover: {
        size: 5,
      },
    },
  };

  return (
    <div className="rounded-xl border border-stroke bg-white p-4.5 sm:p-6 shadow-sm dark:border-strokedark dark:bg-boxdark transition-colors duration-200">
      <div id="chart-temp-curve" className="w-full">
        <ReactApexChart options={options} series={series || []} type="line" height={height} />
      </div>
    </div>
  );
};

export default TempCurveChart;
