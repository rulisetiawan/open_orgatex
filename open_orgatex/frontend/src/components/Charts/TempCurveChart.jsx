import React, { useMemo, useId } from 'react';
import ReactApexChart from 'react-apexcharts';
import { useTheme } from '../../context/ThemeContext';

const TempCurveChart = ({
  series,
  categories,
  title = 'Profil Kurva Suhu Pencelupan (°C)',
  height = 360,
  annotations = {},
}) => {
  const { theme } = useTheme();
  const chartDomId = useId();
  const isDark =
    theme === 'dark' ||
    (typeof document !== 'undefined' && document.documentElement.classList.contains('dark'));

  const options = useMemo(() => {
    // Digital Automation Dashboard trend palette (--green #16866c, --amber #d78b24, --blue #6895a6, --red #d26060)
    const chartColors = isDark
      ? ['#10b981', '#f59e0b', '#38bdf8', '#f87171', '#a855f7']
      : ['#16866c', '#d78b24', '#6895a6', '#d26060', '#7c3aed'];

    const seriesCount = Math.max(1, (series || []).length);
    const fillTypes = Array.from({ length: seriesCount }, (_, i) => (i === 0 ? 'gradient' : 'solid'));
    const fillOpacities = Array.from({ length: seriesCount }, (_, i) => (i === 0 ? 1 : 0));

    return {
      chart: {
        type: 'area',
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
        animations: {
          enabled: true,
          easing: 'easeinout',
          speed: 320,
          dynamicAnimation: {
            enabled: true,
            speed: 220,
          },
        },
      },
      annotations: {
        xaxis: annotations.xaxis || [],
        yaxis: annotations.yaxis || [],
        points: annotations.points || [],
      },
      theme: {
        mode: isDark ? 'dark' : 'light',
      },
      colors: chartColors,
      dataLabels: {
        enabled: false,
      },
      fill: {
        type: fillTypes,
        opacity: fillOpacities,
        gradient: {
          shadeIntensity: 1,
          type: 'vertical',
          opacityFrom: isDark ? 0.28 : 0.22,
          opacityTo: 0.0,
          stops: [0, 92, 100],
        },
      },
      stroke: {
        width: [2.2, 1.8, 1.8, 1.5],
        curve: 'smooth',
        dashArray: [0, 5, 0, 3],
      },
      title: {
        text: title,
        align: 'left',
        style: {
          fontSize: '13px',
          fontWeight: 600,
          color: isDark ? '#eef4f6' : '#183039',
          fontFamily: "'Inter', sans-serif",
        },
      },
      grid: {
        borderColor: isDark ? 'rgba(148, 163, 184, 0.14)' : '#e2e9e9',
        strokeDashArray: 4,
        xaxis: { lines: { show: false } },
        yaxis: { lines: { show: true } },
        padding: {
          top: 8,
          right: 12,
          bottom: 4,
          left: 12,
        },
      },
      xaxis: {
        categories: categories || [],
        title: {
          text: 'Timeline / Langkah Resep',
          style: {
            fontSize: '11px',
            fontWeight: 500,
            color: isDark ? '#8b9eae' : '#77888d',
            fontFamily: "'Inter', sans-serif",
          },
        },
        labels: {
          style: {
            colors: isDark ? '#8b9eae' : '#77888d',
            fontSize: '11px',
            fontWeight: 500,
            fontFamily: "'Inter', sans-serif",
          },
        },
        axisBorder: {
          show: false,
        },
        axisTicks: {
          show: false,
        },
        crosshairs: {
          show: true,
          stroke: {
            color: isDark ? 'rgba(16, 185, 129, 0.35)' : 'rgba(22, 134, 108, 0.35)',
            width: 1,
            dashArray: 3,
          },
        },
      },
      yaxis: {
        min: 0,
        max: 140,
        tickAmount: 7,
        title: {
          text: 'Suhu (°C)',
          style: {
            fontSize: '11px',
            fontWeight: 500,
            color: isDark ? '#8b9eae' : '#77888d',
            fontFamily: "'Inter', sans-serif",
          },
        },
        labels: {
          formatter: (val) => `${Math.round(val)}°`,
          style: {
            colors: isDark ? '#8b9eae' : '#77888d',
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
        fontWeight: 500,
        fontFamily: "'Inter', sans-serif",
        labels: {
          colors: isDark ? '#cbd5e1' : '#183039',
        },
        markers: {
          width: 10,
          height: 10,
          radius: 10,
        },
        itemMargin: {
          horizontal: 10,
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
          formatter: (val) =>
            val !== undefined && val !== null ? `${val} °C` : '0 °C',
        },
      },
      markers: {
        size: 0,
        strokeWidth: 2,
        strokeColors: isDark ? '#0f172a' : '#ffffff',
        hover: {
          size: 5,
        },
      },
    };
  }, [isDark, height, title, categories, annotations, series]);

  return (
    <div className="rounded-xl border border-[#e2e9e9] bg-white p-4 sm:p-5 shadow-xs dark:border-strokedark dark:bg-boxdark transition-colors duration-200">
      <div id={`chart-temp-curve-${chartDomId}`} className="w-full">
        <ReactApexChart options={options} series={series || []} type="area" height={height} />
      </div>
    </div>
  );
};

export default React.memo(TempCurveChart);
