import React from 'react';
import ReactApexChart from 'react-apexcharts';

const TempCurveChart = ({ series, categories, title = "Profil Kurva Suhu Pencelupan (°C)" }) => {
  const options = {
    chart: {
      type: 'line',
      height: 350,
      toolbar: { show: true },
      zoom: { enabled: true },
      fontFamily: 'Satoshi, sans-serif',
      dropShadow: {
        enabled: true,
        color: '#623CEA14',
        top: 10,
        blur: 4,
        left: 0,
        opacity: 0.1,
      },
    },
    colors: ['#3C50E0', '#80CAEE', '#10B981', '#DC3545'],
    stroke: {
      width: [2, 2, 2, 2],
      curve: 'straight',
      dashArray: [0, 5, 0, 0],
    },
    title: {
      text: title,
      align: 'left',
      style: { fontSize: '14px', fontWeight: 600, color: '#1C2434' },
    },
    grid: {
      xaxis: { lines: { show: true } },
      yaxis: { lines: { show: true } },
    },
    xaxis: {
      categories: categories || [],
      title: { text: 'Timeline (Waktu)' },
    },
    yaxis: {
      min: 20,
      max: 140,
      title: { text: 'Suhu (°C)' },
    },
    legend: {
      position: 'top',
      horizontalAlign: 'right',
    },
  };

  return (
    <div className="rounded-sm border border-stroke bg-white px-5 pt-7.5 pb-5 shadow-default dark:border-strokedark dark:bg-boxdark sm:px-7.5">
      <div id="chartOne" className="-ml-5">
        <ReactApexChart options={options} series={series} type="line" height={350} />
      </div>
    </div>
  );
};

export default TempCurveChart;
