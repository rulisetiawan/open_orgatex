import React from 'react';
import Flatpickr from 'react-flatpickr';
import 'flatpickr/dist/themes/material_blue.css';
import { Calendar } from 'lucide-react';

const DatePicker = ({ label, value, onChange, placeholder = "Pilih tanggal..." }) => {
  return (
    <div>
      {label && (
        <label className="mb-2.5 block text-black dark:text-white font-medium text-sm">
          {label}
        </label>
      )}
      <div className="relative">
        <Flatpickr
          value={value}
          onChange={onChange}
          options={{
            dateFormat: "Y-m-d H:i",
            enableTime: true,
            time_24hr: true,
          }}
          className="w-full rounded border-[1.5px] border-stroke bg-transparent py-3 px-5 font-medium outline-none transition focus:border-primary active:border-primary disabled:cursor-default disabled:bg-whiter dark:border-form-strokedark dark:bg-form-input dark:focus:border-primary"
          placeholder={placeholder}
        />
        <div className="pointer-events-none absolute inset-0 left-auto right-4 flex items-center">
          <Calendar className="h-5 w-5 text-body" />
        </div>
      </div>
    </div>
  );
};

export default DatePicker;
